"""Normalize and expose request-scoped spider cookies."""

from __future__ import annotations

from contextvars import ContextVar

COOKIE_MAX_LENGTH = 16384
RUNTIME_COOKIE_FILENAME = "_spider_runtime_cookies"

_cookies_var: ContextVar[str | None] = ContextVar("spider_request_cookies", default=None)


class CookieValidationError(ValueError):
    """Raised when the cookie string is too large or malformed."""


def normalize_cookies(raw: str | None) -> str | None:
    """Trim and validate a Cookie header value; empty → None."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise CookieValidationError("cookies must be a string")
    value = raw.strip()
    if not value:
        return None
    if len(value) > COOKIE_MAX_LENGTH:
        raise CookieValidationError("cookies too long")
    if any(ch in value for ch in ("\r", "\n", "\x00")):
        raise CookieValidationError("cookies contain invalid control characters")
    return value


def set_request_cookies(cookies: str | None) -> None:
    _cookies_var.set(normalize_cookies(cookies) if cookies is not None else None)


def get_request_cookies() -> str | None:
    return _cookies_var.get()


def clear_request_cookies() -> None:
    _cookies_var.set(None)


def cookies_configured() -> bool:
    return bool(get_request_cookies())
