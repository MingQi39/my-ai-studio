from app.spider.services.code_guards import validate_spider_imports
from app.spider.services.spider_pipeline_service import _fallback_playwright_spider_code


def test_rejects_soup_from_playwright_sync_api():
    code = (
        "from playwright.sync_api import sync_playwright, Browser, Page, Soup\n"
        "from bs4 import BeautifulSoup\n"
    )
    result = validate_spider_imports(code, scrape_engine="playwright")
    assert result["valid"] is False
    assert "Soup" in result["message"]


def test_accepts_sync_playwright_and_beautifulsoup():
    code = (
        "from playwright.sync_api import sync_playwright\n"
        "from bs4 import BeautifulSoup\n"
        "import json\n"
    )
    result = validate_spider_imports(code, scrape_engine="playwright")
    assert result["valid"] is True


def test_requests_engine_rejects_playwright_import():
    code = (
        "import requests\n"
        "from bs4 import BeautifulSoup\n"
        "from playwright.sync_api import sync_playwright\n"
    )
    result = validate_spider_imports(code, scrape_engine="requests")
    assert result["valid"] is False
    assert "playwright" in result["message"].lower()


def test_fallback_playwright_template_passes():
    code = _fallback_playwright_spider_code("https://example.com", limit=5)
    result = validate_spider_imports(code, scrape_engine="playwright")
    assert result["valid"] is True
