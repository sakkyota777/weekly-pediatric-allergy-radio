#!/usr/bin/env python3
"""Render a self-contained HTML infographic to a full-page PNG.

Usage:
    python scripts/render_infographic.py <infographic.html> <out.png> [--width 1200]

Uses Playwright driving the Chromium that ships with this environment
(PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers). The HTML must be fully
self-contained (inline CSS/JS, no external network requests), because the
render runs offline.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys


def die(msg: str, code: int = 1) -> None:
    print(f"[render_infographic] ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def main() -> None:
    ap = argparse.ArgumentParser(description="HTML infographic -> full-page PNG")
    ap.add_argument("html", help="path to the self-contained .html infographic")
    ap.add_argument("out", help="output .png path")
    ap.add_argument("--width", type=int, default=1200, help="viewport width in px")
    args = ap.parse_args()

    html_path = pathlib.Path(args.html).resolve()
    if not html_path.exists():
        die(f"html not found: {html_path}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        die("playwright not installed. Run: pip install -r scripts/requirements.txt")

    # Prefer the bundled Chromium; fall back to Playwright's own resolution.
    exe = None
    bundled = pathlib.Path("/opt/pw-browsers/chromium")
    if bundled.exists():
        exe = str(bundled)

    with sync_playwright() as p:
        launch_kwargs = {"args": ["--no-sandbox"]}
        if exe:
            launch_kwargs["executable_path"] = exe
        try:
            browser = p.chromium.launch(**launch_kwargs)
        except Exception as exc:  # noqa: BLE001 - surface a clear message
            die(f"failed to launch Chromium: {exc}")
        page = browser.new_page(viewport={"width": args.width, "height": 900},
                                device_scale_factor=2)
        page.goto(html_path.as_uri())
        page.wait_for_load_state("networkidle")
        page.screenshot(path=args.out, full_page=True)
        browser.close()

    size = os.path.getsize(args.out)
    print(f"[render_infographic] wrote {args.out} ({size // 1024} KiB)")


if __name__ == "__main__":
    main()
