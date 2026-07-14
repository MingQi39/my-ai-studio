from app.spider.services.request_cookies import RUNTIME_COOKIE_FILENAME
from app.spider.services.sandbox import list_workspace_files
from app.spider.services.spider_pipeline_service import (
    _fallback_playwright_spider_code,
    _fallback_spider_code,
)


class _FakeWorkspace:
    def list_files(self):
        return [
            {"name": "spider.py", "size": 10},
            {"name": RUNTIME_COOKIE_FILENAME, "size": 20},
            {"name": "source_page.meta.json", "size": 5},
            {"name": "scraped_data.json", "size": 8},
        ]


def test_list_workspace_files_hides_runtime_cookies():
    files = list_workspace_files(_FakeWorkspace())
    names = {item["name"] for item in files}
    assert "spider.py" in names
    assert "scraped_data.json" in names
    assert RUNTIME_COOKIE_FILENAME not in names
    assert "source_page.meta.json" not in names


def test_fallback_templates_read_spider_cookie_env():
    http_code = _fallback_spider_code("https://example.com/list")
    assert "SPIDER_COOKIE" in http_code
    assert "os.environ.get(\"SPIDER_COOKIE\")" in http_code or "os.environ.get('SPIDER_COOKIE')" in http_code
    assert "SUB=" not in http_code

    pw_code = _fallback_playwright_spider_code("https://example.com/list")
    assert "SPIDER_COOKIE" in pw_code
    assert "set_extra_http_headers" in pw_code
