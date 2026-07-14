from app.spider.services.request_cookies import clear_request_cookies, set_request_cookies
from app.spider.services.tools import get_safe_headers


def test_get_safe_headers_includes_cookie_when_configured():
    clear_request_cookies()
    try:
        set_request_cookies("SUB=abc; SUBP=xyz")
        headers = get_safe_headers("https://www.weibo.com/")
        assert headers["Cookie"] == "SUB=abc; SUBP=xyz"
        assert "User-Agent" in headers
    finally:
        clear_request_cookies()


def test_get_safe_headers_omits_cookie_when_unset():
    clear_request_cookies()
    headers = get_safe_headers("https://example.com/")
    assert "Cookie" not in headers
