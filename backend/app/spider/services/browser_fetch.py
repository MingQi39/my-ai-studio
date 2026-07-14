"""Sandbox Playwright probe and page fetch helpers."""

from __future__ import annotations

import json
import shlex
from typing import Any

PLAYWRIGHT_FETCH_SCRIPT = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sys

from playwright.sync_api import sync_playwright

TARGET_URL = sys.argv[1] if len(sys.argv) > 1 else ""


def main() -> int:
    if not TARGET_URL:
        print("missing TARGET_URL", file=sys.stderr)
        return 1
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
            html = page.content()
        finally:
            browser.close()
    with open("source_page.html", "w", encoding="utf-8") as f:
        f.write(html)
    meta = {"url": TARGET_URL, "fetch_mode": "playwright"}
    with open("source_page.meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    print("fetched", len(html), "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def probe_playwright_available(workspace: Any) -> bool:
    backend = workspace.backend
    result = backend.execute(
        'python -c "from playwright.sync_api import sync_playwright; print(\'ok\')"'
    )
    exit_code = getattr(result, "exit_code", 1)
    try:
        return int(exit_code) == 0
    except (TypeError, ValueError):
        return False


def run_playwright_fetch(workspace: Any, url: str) -> dict[str, Any]:
    workspace.write_text("playwright_fetch.py", PLAYWRIGHT_FETCH_SCRIPT)
    working_dir = getattr(workspace.backend, "working_dir", "/workspace")
    quoted = shlex.quote(url)
    cmd = f"cd {shlex.quote(working_dir)} && python playwright_fetch.py {quoted}"
    exec_result = workspace.backend.execute(cmd)
    raw_exit = getattr(exec_result, "exit_code", 1)
    try:
        exit_code = int(raw_exit)
    except (TypeError, ValueError):
        exit_code = 1
    output = getattr(exec_result, "output", "") or ""
    html = workspace.read_text("source_page.html")
    success = exit_code == 0 and bool(html)
    return {
        "success": success,
        "html_file": "source_page.html" if html else "",
        "html_content": html or "",
        "error": None if success else (output.strip() or f"exit_code={exit_code}"),
        "output_preview": (output or "")[:500],
        "fetch_mode": "playwright",
    }
