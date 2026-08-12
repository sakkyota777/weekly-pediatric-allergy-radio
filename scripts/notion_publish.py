#!/usr/bin/env python3
"""Publish a weekly issue to Notion via the REST API (connector-free).

This replaces the Notion MCP so the weekly pipeline can run unattended in a
fired cloud session (which has no MCP connectors). It talks to api.notion.com
directly with an internal-integration token.

Requirements (environment):
  - NOTION_API_KEY   : Notion internal integration token ("ntn_..."/"secret_...")
  - NOTION_PARENT_ID : target database / data-source id
                       (default: the project's "各号" DB)
  - NOTION_VERSION   : API version header (default 2022-06-28)
  The integration must be shared with the target database (Notion → the DB →
  ... → Connections → add your integration), and the environment's network
  policy must allow egress to api.notion.com.

Input: a JSON payload the agent writes, e.g. reports/<DATE>/notion_payload.json
  {
    "title": "2026-08-01 号",
    "date": "2026-08-01",
    "topic_count": 5,
    "pmids": ["...", "..."],
    "intro": "出典: According to PubMed / 検索: ...",
    "infographic_image_url": "https://raw.githubusercontent.com/<owner>/<repo>/main/reports/<DATE>/infographic.png",
    "mp3_url": "https://raw.githubusercontent.com/.../radio.mp3",   // or null
    "articles": [
      {"title":"...","journal":"...","date":"...","pmid":"...","doi":"...","summary":"..."},
      ...
    ]
  }

Usage:
    python scripts/notion_publish.py reports/<DATE>/notion_payload.json
    python scripts/notion_publish.py payload.json --dry-run   # print, no network/token
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import requests

API = "https://api.notion.com/v1"
DEFAULT_PARENT = os.environ.get(
    "NOTION_PARENT_ID", "1a961a49-2238-4dcb-87fc-53c23ffcb5d7"
)
VERSION = os.environ.get("NOTION_VERSION", "2022-06-28")
TIMEOUT = 60

# Map logical fields -> the Notion property NAME in the target DB. Setting is
# still type-checked against the live schema, so a rename here is all it takes.
PROP_TITLE = "週"
PROP_DATE = "公開日"
PROP_TOPICS = "トピック数"
PROP_PMIDS = "PMIDs"
PROP_MP3 = "MP3"
PROP_PNG = "インフォグラフィックPNG"
PROP_POSTED = "Notion掲載"


def die(msg: str, code: int = 1) -> None:
    print(f"[notion] ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def _headers(key: str) -> dict:
    return {
        "Authorization": f"Bearer {key}",
        "Notion-Version": VERSION,
        "Content-Type": "application/json",
    }


def _rt(text: str) -> list:
    """Rich-text array, chunked to stay under Notion's 2000-char/segment limit."""
    text = text or ""
    segs = [text[i:i + 1900] for i in range(0, len(text), 1900)] or [""]
    return [{"type": "text", "text": {"content": s}} for s in segs]


def get_schema(key: str, parent_id: str) -> dict:
    """Return {prop_name: prop_type} for the target DB, or {} if unreadable."""
    for path in (f"databases/{parent_id}", f"data_sources/{parent_id}"):
        resp = requests.get(f"{API}/{path}", headers=_headers(key), timeout=TIMEOUT)
        if resp.status_code == 200:
            props = resp.json().get("properties", {})
            return {name: p.get("type") for name, p in props.items()}
        if resp.status_code in (401, 403):
            die(f"Notion auth/permission failed ({resp.status_code}). Is NOTION_API_KEY "
                f"set and the integration shared with the DB? Body: {resp.text[:300]}")
    return {}


def build_properties(payload: dict, schema: dict) -> dict:
    """Build the Notion `properties` object, honoring each property's real type."""
    props: dict = {}

    def set_prop(name: str, value) -> None:
        ptype = schema.get(name)
        if ptype is None:
            return  # property absent in this DB; skip quietly
        if ptype == "title":
            props[name] = {"title": _rt(str(value))}
        elif ptype == "rich_text":
            props[name] = {"rich_text": _rt(str(value))}
        elif ptype == "number":
            props[name] = {"number": value}
        elif ptype == "date":
            props[name] = {"date": {"start": str(value)}}
        elif ptype == "url":
            props[name] = {"url": (str(value) if value else None)}
        elif ptype == "checkbox":
            props[name] = {"checkbox": bool(value)}
        elif ptype == "select":
            props[name] = {"select": {"name": str(value)}}

    set_prop(PROP_TITLE, payload.get("title", payload.get("date", "")))
    set_prop(PROP_DATE, payload.get("date"))
    set_prop(PROP_TOPICS, payload.get("topic_count"))
    set_prop(PROP_PMIDS, ", ".join(payload.get("pmids", [])))
    if payload.get("mp3_url"):
        set_prop(PROP_MP3, payload["mp3_url"])
    if payload.get("infographic_image_url"):
        set_prop(PROP_PNG, payload["infographic_image_url"])
    set_prop(PROP_POSTED, True)
    return props


def build_children(payload: dict) -> list:
    children: list = []
    if payload.get("intro"):
        children.append({
            "object": "block", "type": "quote",
            "quote": {"rich_text": _rt(payload["intro"])},
        })
    if payload.get("infographic_image_url"):
        children.append({
            "object": "block", "type": "image",
            "image": {"type": "external",
                      "external": {"url": payload["infographic_image_url"]}},
        })
    children.append({
        "object": "block", "type": "heading_2",
        "heading_2": {"rich_text": _rt("今週のトピック")},
    })
    for i, a in enumerate(payload.get("articles", []), 1):
        children.append({
            "object": "block", "type": "heading_3",
            "heading_3": {"rich_text": _rt(f"{i}. {a.get('title','')}")},
        })
        meta = " ・ ".join(x for x in [
            a.get("journal", ""), a.get("date", ""),
            f"PMID {a['pmid']}" if a.get("pmid") else "",
            f"DOI {a['doi']}" if a.get("doi") else "",
        ] if x)
        children.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text",
                          "text": {"content": meta},
                          "annotations": {"italic": True}}]},
        })
        children.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": _rt(a.get("summary", ""))},
        })
    children.append({"object": "block", "type": "divider", "divider": {}})
    if payload.get("mp3_url"):
        children.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [
                {"type": "text", "text": {"content": "🔊 今週号の音声(MP3): "}},
                {"type": "text",
                 "text": {"content": payload["mp3_url"],
                          "link": {"url": payload["mp3_url"]}}},
            ]},
        })
    else:
        children.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": _rt("🔊 音声(MP3)は未生成です。")},
        })
    return children


def build_parent(schema_ok: bool, parent_id: str) -> dict:
    # 2022-06-28 uses database_id; newer versions accept data_source_id.
    if VERSION >= "2025-09-03":
        return {"type": "data_source_id", "data_source_id": parent_id}
    return {"database_id": parent_id}


def main() -> None:
    ap = argparse.ArgumentParser(description="Publish a weekly issue to Notion (REST)")
    ap.add_argument("payload", help="path to notion_payload.json")
    ap.add_argument("--parent", default=DEFAULT_PARENT, help="database / data-source id")
    ap.add_argument("--dry-run", action="store_true", help="print request; no token/network")
    args = ap.parse_args()

    with open(args.payload, "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    if args.dry_run:
        body = {
            "parent": build_parent(True, args.parent),
            "properties": build_properties(payload, {
                PROP_TITLE: "title", PROP_DATE: "date", PROP_TOPICS: "number",
                PROP_PMIDS: "rich_text", PROP_MP3: "url", PROP_PNG: "url",
                PROP_POSTED: "checkbox",
            }),
            "children": build_children(payload),
        }
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return

    key = os.environ.get("NOTION_API_KEY")
    if not key:
        die("NOTION_API_KEY is not set. Add it to the environment (Notion internal "
            "integration token) and share the target DB with the integration.", code=2)

    schema = get_schema(key, args.parent)
    if not schema:
        die(f"Could not read the DB schema for parent {args.parent}. Check that the "
            f"integration is shared with it and the id is correct.")

    body = {
        "parent": build_parent(bool(schema), args.parent),
        "properties": build_properties(payload, schema),
        "children": build_children(payload),
    }
    resp = requests.post(f"{API}/pages", headers=_headers(key), json=body, timeout=TIMEOUT)
    if resp.status_code == 200:
        page = resp.json()
        print(f"[notion] created page: {page.get('url')}")
        print(page.get("id", ""))
        return
    die(f"create page failed HTTP {resp.status_code}: {resp.text[:600]}")


if __name__ == "__main__":
    main()
