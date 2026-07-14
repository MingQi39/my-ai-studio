import ast

from app.spider.services.spider_pipeline_service import _fallback_playwright_spider_code


def test_fallback_playwright_template_is_valid_python():
    code = _fallback_playwright_spider_code("https://example.com/list", limit=5)
    ast.parse(code)
    assert "sync_playwright" in code
    assert "BeautifulSoup" in code
    assert "scraped_data.json" in code
    assert "https://example.com/list" in code
    assert "requests.Session" not in code
