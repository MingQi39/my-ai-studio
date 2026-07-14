import ast
import sys
from pathlib import Path
from types import ModuleType

from bs4 import BeautifulSoup

from app.spider.services.spider_pipeline_service import _fallback_playwright_spider_code

SIDE_LIST_HTML = """
<html><body>
  <div class="hotBand">
    <a href="//s.weibo.com/weibo?q=%23topic1%23">习近平将出席世界人工智能大会开幕式</a>
    <a href="//s.weibo.com/weibo?q=%23topic2%23">1 请愿逐出阿根廷人数已超500万 182.3万</a>
    <a href="//s.weibo.com/weibo?q=%23topic3%23">2 AI杀死时尚行业 92.4万</a>
  </div>
  <article class="feed">
    <a href="//weibo.com/u/123"> </a>
  </article>
</body></html>
"""


def _stub_playwright(monkeypatch) -> None:
    pkg = ModuleType("playwright")
    sync_api = ModuleType("playwright.sync_api")

    def _sync_playwright():
        raise AssertionError("sync_playwright should not run in unit tests")

    sync_api.sync_playwright = _sync_playwright
    monkeypatch.setitem(sys.modules, "playwright", pkg)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)


def _load_module(code: str, monkeypatch) -> dict:
    _stub_playwright(monkeypatch)
    ns: dict = {}
    exec(compile(ast.parse(code), "<pw-fallback>", "exec"), ns)
    return ns


def test_fallback_playwright_template_is_valid_python():
    code = _fallback_playwright_spider_code("https://example.com/list", limit=5)
    ast.parse(code)
    assert "sync_playwright" in code
    assert "BeautifulSoup" in code
    assert "scraped_data.json" in code
    assert "https://example.com/list" in code
    assert "requests.Session" not in code


def test_fallback_playwright_prefers_existing_source_page_and_waits():
    code = _fallback_playwright_spider_code("https://example.com/list", limit=5)
    assert "source_page.html" in code
    assert "networkidle" in code
    assert 'wait_until="domcontentloaded"' in code or "wait_until='domcontentloaded'" in code


def test_fallback_playwright_parse_requires_nonempty_title(monkeypatch):
    code = _fallback_playwright_spider_code("https://example.com/list", limit=5)
    parse_items = _load_module(code, monkeypatch)["parse_items"]
    items = parse_items(BeautifulSoup(SIDE_LIST_HTML, "lxml"))
    assert len(items) >= 1
    assert all(item["title"].strip() for item in items)
    assert all(item["url"].strip() for item in items)
    # Must not lock onto empty-title feed user links
    assert not any(item["url"].endswith("/u/123") for item in items)


def test_fallback_playwright_main_uses_local_html_without_browser(tmp_path: Path, monkeypatch):
    code = _fallback_playwright_spider_code("https://example.com/list", limit=5)
    ns = _load_module(code, monkeypatch)

    monkeypatch.chdir(tmp_path)
    (tmp_path / "source_page.html").write_text(SIDE_LIST_HTML, encoding="utf-8")

    def boom(*_a, **_k):
        raise AssertionError("must not launch browser when source_page.html exists")

    monkeypatch.setattr(ns["fetch_html"], "__call__", boom, raising=False)
    ns["fetch_html"] = boom
    assert ns["main"]() == 0
    saved = (tmp_path / "scraped_data.json").read_text(encoding="utf-8")
    assert "习近平" in saved or "请愿" in saved or "AI杀死" in saved
