"""Resolve spider target URL from request fields."""

from __future__ import annotations


def try_resolve_spider_target_url(message: str, target_url: str | None) -> str | None:
    if target_url and target_url.strip():
        return target_url.strip()
    for token in (message or "").split():
        if token.startswith("http://") or token.startswith("https://"):
            return token.strip(".,;)")
    return None
