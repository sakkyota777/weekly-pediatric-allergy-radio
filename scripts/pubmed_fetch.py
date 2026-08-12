#!/usr/bin/env python3
"""Fetch pediatric-kidney-disease candidate articles from PubMed via E-utilities.

This is the connector-free (token-optional) replacement for the PubMed MCP,
so the weekly pipeline can run unattended in a fired cloud session that has no
MCP connectors. It hits the public NCBI E-utilities HTTP API — no key is
required, though setting NCBI_API_KEY raises the rate limit.

Usage:
    python scripts/pubmed_fetch.py --days 7 --max 30 --out reports/<DATE>/candidates.json
    python scripts/pubmed_fetch.py --date-to 2026-07-25 --days 7 --out candidates.json

Output: a JSON array of candidates, each with pmid, title, journal, pubdate,
doi, authors, url and abstract. The agent reads this file, selects 3-5, and
writes reports/<DATE>/articles.json itself.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import time
import xml.etree.ElementTree as ET

import requests

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL = "weekly_reports_pediatric_kidney"
EMAIL = os.environ.get("NCBI_EMAIL", "")
API_KEY = os.environ.get("NCBI_API_KEY", "")

DEFAULT_QUERY = (
    "(pediatric OR paediatric OR children OR childhood) AND "
    "(kidney disease OR nephrology OR nephrotic OR nephritis OR renal)"
)
TIMEOUT = 60
MAX_RETRIES = 4


def _common_params() -> dict:
    p = {"tool": TOOL}
    if EMAIL:
        p["email"] = EMAIL
    if API_KEY:
        p["api_key"] = API_KEY
    return p


def _get(path: str, params: dict) -> requests.Response:
    url = f"{EUTILS}/{path}"
    merged = {**_common_params(), **params}
    last = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=merged, timeout=TIMEOUT)
            if resp.status_code == 200:
                return resp
            last = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except requests.RequestException as exc:
            last = str(exc)
        sleep_s = 2 ** (attempt + 1)
        print(f"[pubmed] retry {attempt + 1}/{MAX_RETRIES} after {sleep_s}s ({last})",
              file=sys.stderr)
        time.sleep(sleep_s)
    print(f"[pubmed] ERROR: {path} failed after {MAX_RETRIES} retries: {last}",
          file=sys.stderr)
    sys.exit(1)


def esearch(query: str, date_from: str, date_to: str, retmax: int) -> list[str]:
    """Return a list of PMIDs collated by PubMed collation date (edat)."""
    params = {
        "db": "pubmed",
        "term": query,
        "datetype": "edat",
        "mindate": date_from.replace("-", "/"),
        "maxdate": date_to.replace("-", "/"),
        "retmax": str(retmax),
        "sort": "pub+date",
        "retmode": "json",
    }
    data = _get("esearch.fcgi", params).json()
    return data.get("esearchresult", {}).get("idlist", [])


def efetch_abstracts(pmids: list[str]) -> dict[str, dict]:
    """Return {pmid: {title, journal, pubdate, doi, authors, abstract}} via efetch XML."""
    if not pmids:
        return {}
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"}
    xml = _get("efetch.fcgi", params).text
    root = ET.fromstring(xml)
    out: dict[str, dict] = {}
    for art in root.findall(".//PubmedArticle"):
        pmid_el = art.find(".//PMID")
        if pmid_el is None or not pmid_el.text:
            continue
        pmid = pmid_el.text.strip()

        title_el = art.find(".//ArticleTitle")
        title = "".join(title_el.itertext()).strip() if title_el is not None else ""

        journal = art.findtext(".//Journal/ISOAbbreviation") or \
            art.findtext(".//Journal/Title") or ""

        # Publication date: prefer ArticleDate, fall back to JournalIssue PubDate.
        pubdate = _extract_pubdate(art)

        doi = ""
        for eid in art.findall(".//ArticleIdList/ArticleId"):
            if eid.get("IdType") == "doi" and eid.text:
                doi = eid.text.strip()
                break
        if not doi:
            eloc = art.find(".//ELocationID[@EIdType='doi']")
            if eloc is not None and eloc.text:
                doi = eloc.text.strip()

        authors = []
        for a in art.findall(".//AuthorList/Author"):
            last = a.findtext("LastName")
            init = a.findtext("Initials")
            if last:
                authors.append(f"{last} {init}".strip())
        authors_str = ", ".join(authors[:6]) + (" et al." if len(authors) > 6 else "")

        # Abstract: join all AbstractText sections (with optional labels).
        parts = []
        for ab in art.findall(".//Abstract/AbstractText"):
            label = ab.get("Label")
            text = "".join(ab.itertext()).strip()
            parts.append(f"{label}: {text}" if label else text)
        abstract = "\n".join(p for p in parts if p)

        pub_types = [pt.text for pt in art.findall(".//PublicationTypeList/PublicationType")
                     if pt.text]

        out[pmid] = {
            "pmid": pmid,
            "title": title,
            "journal": journal,
            "pubdate": pubdate,
            "doi": doi,
            "authors": authors_str,
            "publication_types": pub_types,
            "abstract": abstract,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        }
    return out


def _extract_pubdate(art: ET.Element) -> str:
    ad = art.find(".//ArticleDate")
    if ad is not None:
        y, m, d = ad.findtext("Year"), ad.findtext("Month"), ad.findtext("Day")
        if y:
            return f"{y}-{(m or '01').zfill(2)}-{(d or '01').zfill(2)}"
    pd = art.find(".//JournalIssue/PubDate")
    if pd is not None:
        y = pd.findtext("Year") or ""
        m = pd.findtext("Month") or ""
        d = pd.findtext("Day") or ""
        month_map = {"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05",
                     "Jun": "06", "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10",
                     "Nov": "11", "Dec": "12"}
        m = month_map.get(m[:3], m.zfill(2) if m.isdigit() else "")
        parts = [p for p in (y, m, d.zfill(2) if d.isdigit() else "") if p]
        return "-".join(parts)
    return ""


def main() -> None:
    ap = argparse.ArgumentParser(description="Fetch PubMed candidates (E-utilities, connector-free)")
    ap.add_argument("--query", default=DEFAULT_QUERY, help="PubMed search term")
    ap.add_argument("--date-to", default=None, help="end date YYYY-MM-DD (default: today UTC)")
    ap.add_argument("--days", type=int, default=7, help="window size in days (default 7)")
    ap.add_argument("--max", type=int, default=30, help="max candidates (default 30)")
    ap.add_argument("--out", required=True, help="output JSON path")
    args = ap.parse_args()

    date_to = args.date_to or _dt.datetime.utcnow().strftime("%Y-%m-%d")
    d_to = _dt.datetime.strptime(date_to, "%Y-%m-%d")
    date_from = (d_to - _dt.timedelta(days=args.days)).strftime("%Y-%m-%d")

    print(f"[pubmed] searching {date_from}..{date_to} (edat), max={args.max}")
    pmids = esearch(args.query, date_from, date_to, args.max)
    print(f"[pubmed] {len(pmids)} PMIDs")
    meta = efetch_abstracts(pmids)
    # Preserve esearch ordering (newest first by pub date).
    candidates = [meta[p] for p in pmids if p in meta]

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({
            "query": args.query,
            "date_from": date_from,
            "date_to": date_to,
            "count": len(candidates),
            "candidates": candidates,
        }, fh, ensure_ascii=False, indent=2)
    print(f"[pubmed] wrote {args.out} ({len(candidates)} candidates)")


if __name__ == "__main__":
    main()
