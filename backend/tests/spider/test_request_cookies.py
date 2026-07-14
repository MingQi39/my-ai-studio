import pytest

from app.spider.services.request_cookies import (
    COOKIE_MAX_LENGTH,
    CookieValidationError,
    clear_request_cookies,
    cookies_configured,
    get_request_cookies,
    normalize_cookies,
    set_request_cookies,
)


def test_normalize_empty_and_whitespace_to_none():
    assert normalize_cookies(None) is None
    assert normalize_cookies("") is None
    assert normalize_cookies("   ") is None


def test_normalize_trims_valid_cookie():
    assert normalize_cookies("  SUB=abc; SUBP=xyz  ") == "SUB=abc; SUBP=xyz"


def test_normalize_rejects_too_long():
    with pytest.raises(CookieValidationError):
        normalize_cookies("x" * (COOKIE_MAX_LENGTH + 1))


def test_normalize_rejects_newlines():
    with pytest.raises(CookieValidationError):
        normalize_cookies("a=1\nb=2")


def test_contextvar_set_get_clear():
    clear_request_cookies()
    assert get_request_cookies() is None
    assert cookies_configured() is False

    set_request_cookies("  SID=1  ")
    assert get_request_cookies() == "SID=1"
    assert cookies_configured() is True

    clear_request_cookies()
    assert get_request_cookies() is None
