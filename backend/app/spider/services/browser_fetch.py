"""Sandbox Playwright probe and page fetch helpers."""

from __future__ import annotations

import json
import shlex
from typing import Any

PLAYWRIGHT_FETCH_SCRIPT = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import sys
import time
import traceback

from playwright.sync_api import sync_playwright

TARGET_URL = sys.argv[1] if len(sys.argv) > 1 else ""
COOKIE = os.environ.get("SPIDER_COOKIE") or ""
LAUNCH_ARGS = [
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-gpu",
    "--disable-software-rasterizer",
]


def _read_html(page) -> str:
    """Prefer page.content(); fall back when SPA navigations tear down the CDT context."""
    try:
        return page.content()
    except Exception:
        return page.evaluate("() => document.documentElement.outerHTML")


def main() -> int:
    if not TARGET_URL:
        print("missing TARGET_URL", file=sys.stderr)
        return 1
    html = ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=LAUNCH_ARGS)
            try:
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 720},
                    ignore_https_errors=True,
                )
                if COOKIE:
                    context.set_extra_http_headers({"Cookie": COOKIE})
                page = context.new_page()
                page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
                # Allow SPA boot / soft redirects to settle before snapshot.
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
                time.sleep(0.8)
                html = _read_html(page)
                context.close()
            finally:
                browser.close()
    except Exception as exc:
        print(f"playwright_fetch failed: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1

    if not html or not html.strip():
        print("empty html after playwright fetch", file=sys.stderr)
        return 1

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


def _exit_ok(result: Any) -> bool:
    exit_code = getattr(result, "exit_code", 1)
    try:
        return int(exit_code) == 0
    except (TypeError, ValueError):
        return False


def _probe_playwright_import(workspace: Any) -> bool:
    result = workspace.backend.execute(
        'python -c "from playwright.sync_api import sync_playwright; print(\'ok\')"'
    )
    return _exit_ok(result)


def _playwright_browsers_present(workspace: Any) -> bool:
    """Official mcr.microsoft.com/playwright/python images ship browsers under /ms-playwright."""
    result = workspace.backend.execute(
        'test -d "${PLAYWRIGHT_BROWSERS_PATH:-/ms-playwright}" '
        '&& test -n "$(ls -A "${PLAYWRIGHT_BROWSERS_PATH:-/ms-playwright}" 2>/dev/null)"'
    )
    return _exit_ok(result)


def _install_playwright_python_package(workspace: Any) -> bool:
    """Install Playwright Python driver only; do not run `playwright install` (browsers are image-baked)."""
    result = workspace.backend.execute(
        "python -m pip install --no-cache-dir playwright 2>&1"
    )
    return _exit_ok(result)


def probe_playwright_available(workspace: Any) -> bool:
    """Return True if the sandbox can import Playwright.

    Official Playwright Python images include Chromium under /ms-playwright but may
    omit the `playwright` pip package. When browsers are present, attempt a one-shot
    `pip install playwright` before declaring the image unavailable.
    """
    if _probe_playwright_import(workspace):
        return True
    if not _playwright_browsers_present(workspace):
        return False
    if not _install_playwright_python_package(workspace):
        return False
    return _probe_playwright_import(workspace)


def run_playwright_fetch(workspace: Any, url: str) -> dict[str, Any]:
    from app.spider.services.request_cookies import RUNTIME_COOKIE_FILENAME, get_request_cookies

    workspace.write_text("playwright_fetch.py", PLAYWRIGHT_FETCH_SCRIPT)
    working_dir = getattr(workspace.backend, "working_dir", "/workspace")
    quoted = shlex.quote(url)
    cookie = get_request_cookies()
    if cookie:
        workspace.write_text(RUNTIME_COOKIE_FILENAME, cookie)
        cookie_export = (
            f'export SPIDER_COOKIE="$(cat {shlex.quote(RUNTIME_COOKIE_FILENAME)} 2>/dev/null)"; '
        )
    else:
        cookie_export = ""
    cmd = (
        f"cd {shlex.quote(working_dir)} && {cookie_export}"
        f"python playwright_fetch.py {quoted}"
    )
    try:
        exec_result = workspace.backend.execute(cmd)
    finally:
        if cookie:
            workspace.backend.execute(f"rm -f {shlex.quote(RUNTIME_COOKIE_FILENAME)}")
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
