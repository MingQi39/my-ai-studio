"""AST-based import allowlists for LLM-generated spider scripts."""
from __future__ import annotations

import ast
import textwrap
from typing import Any

_BS4_ALLOWED = frozenset({"BeautifulSoup", "Tag"})
_PLAYWRIGHT_SYNC_ALLOWED = frozenset({"sync_playwright"})
_STDLIB_ROOTS = frozenset(
    {
        "json",
        "logging",
        "os",
        "random",
        "re",
        "sys",
        "time",
        "typing",
        "urllib",
        "pathlib",
        "collections",
        "datetime",
        "hashlib",
        "html",
        "io",
        "math",
        "copy",
        "dataclasses",
        "enum",
        "functools",
        "itertools",
        "operator",
        "string",
        "tempfile",
        "traceback",
        "uuid",
        "warnings",
        "base64",
        "csv",
        "textwrap",
    }
)


def validate_spider_imports(code: str, *, scrape_engine: str) -> dict[str, Any]:
    cleaned = textwrap.dedent(code).strip()
    try:
        tree = ast.parse(cleaned)
    except SyntaxError as exc:
        return {
            "valid": False,
            "errors": [{"line": exc.lineno, "message": exc.msg, "text": exc.text}],
            "message": f"语法错误: {exc.msg}",
        }

    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                errors.extend(_check_import_name(alias.name, scrape_engine=scrape_engine))
        elif isinstance(node, ast.ImportFrom):
            errors.extend(_check_import_from(node, scrape_engine=scrape_engine))

    if errors:
        return {
            "valid": False,
            "errors": errors,
            "message": "非法导入: " + "; ".join(errors),
        }
    return {"valid": True, "errors": [], "message": "导入校验通过"}


def _check_import_name(mod: str, *, scrape_engine: str) -> list[str]:
    root = mod.split(".", 1)[0]
    if root == "Soup" or mod == "Soup":
        return ["禁止 import Soup（请用 from bs4 import BeautifulSoup）"]
    if root in {"playwright", "selenium"}:
        if scrape_engine == "requests":
            return [f"requests 引擎禁止导入 {mod}"]
        if root == "playwright":
            return [
                "禁止 import playwright；请用 from playwright.sync_api import sync_playwright"
            ]
        return [f"禁止导入 {mod}"]
    if root == "requests":
        return []
    if root == "bs4":
        return ["请用 from bs4 import BeautifulSoup，不要 import bs4"]
    if root in _STDLIB_ROOTS:
        return []
    if root in {"lxml", "httpx", "aiohttp"}:
        if root in {"httpx", "aiohttp"} and scrape_engine == "requests":
            return [f"requests 引擎禁止 {root}（保持同步 requests）"]
        if root == "aiohttp":
            return ["禁止 aiohttp（必须同步）"]
        return []
    return [f"不允许的模块: {mod}"]


def _check_import_from(node: ast.ImportFrom, *, scrape_engine: str) -> list[str]:
    if node.module is None:
        return ["不支持相对导入"]
    mod = node.module
    names = [a.name for a in node.names]
    errs: list[str] = []

    if "Soup" in names:
        errs.append("禁止导入 Soup（请用 from bs4 import BeautifulSoup）")

    if mod == "bs4" or mod.startswith("bs4."):
        bad = [n for n in names if n != "*" and n not in _BS4_ALLOWED]
        if "*" in names:
            errs.append("禁止 from bs4 import *")
        if bad:
            errs.append(f"bs4 仅允许 {_BS4_ALLOWED}，禁止: {bad}")
        return errs

    if mod.startswith("playwright") or mod == "selenium" or mod.startswith("selenium."):
        if scrape_engine == "requests":
            errs.append(f"requests 引擎禁止导入 {mod}")
            return errs
        if mod != "playwright.sync_api":
            errs.append(
                "Playwright 仅允许 from playwright.sync_api import sync_playwright"
            )
            return errs
        bad = [n for n in names if n != "*" and n not in _PLAYWRIGHT_SYNC_ALLOWED]
        if "*" in names:
            errs.append("禁止 from playwright.sync_api import *")
        if bad:
            errs.append(
                f"playwright.sync_api 仅允许 {_PLAYWRIGHT_SYNC_ALLOWED}，禁止: {bad}"
            )
        return errs

    if mod == "requests" or mod.startswith("requests."):
        return errs

    root = mod.split(".", 1)[0]
    if root in _STDLIB_ROOTS:
        return errs
    if root in {"lxml"}:
        return errs
    if root in {"aiohttp", "httpx"}:
        errs.append(f"禁止导入 {mod}（保持同步）")
        return errs

    errs.append(f"不允许的模块: {mod}")
    return errs
