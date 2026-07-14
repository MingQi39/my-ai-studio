"""Prepare scraped HTML for in-app preview (relative URLs + hotlink Referer)."""

from __future__ import annotations

import base64
import ipaddress
import re
from typing import Callable
from urllib.parse import urljoin, urlparse
from collections import Counter

from bs4 import BeautifulSoup

FetchAsset = Callable[[str, str | None], tuple[bytes, str]]

_MAX_INLINE_ASSETS = 80
_MAX_ASSET_BYTES = 2 * 1024 * 1024

_PRIVATE_HOST_MARKERS = (
    "localhost",
    "metadata.google.internal",
)


def infer_base_url(html: str, fallback: str | None) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    canonical = soup.find("link", rel=lambda value: value and "canonical" in value)
    if canonical and canonical.get("href"):
        return str(canonical["href"]).strip() or fallback

    og = soup.find("meta", attrs={"property": "og:url"})
    if og and og.get("content"):
        return str(og["content"]).strip() or fallback

    if fallback:
        return fallback

    # Last resort: most common absolute page-link origin (skip CDN/image hosts).
    origins: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if not re.match(r"^https?://", href, re.I):
            continue
        parsed = urlparse(href)
        host = (parsed.hostname or "").lower()
        if not host:
            continue
        if any(token in host for token in ("cdn.", "static.", "img.", "doubanio", "googleapis", "accounts.")):
            continue
        origins.append(f"{parsed.scheme}://{parsed.netloc}/")
    if not origins:
        return None
    return Counter(origins).most_common(1)[0][0]


def resolve_resource_url(base_url: str | None, src: str) -> str | None:
    raw = (src or "").strip()
    if not raw or raw.startswith(("data:", "blob:", "javascript:", "{{")):
        return None
    if raw.startswith("//"):
        scheme = "https"
        if base_url:
            parsed = urlparse(base_url)
            if parsed.scheme in ("http", "https"):
                scheme = parsed.scheme
        return f"{scheme}:{raw}"
    if re.match(r"^https?://", raw, re.I):
        return raw
    if not base_url:
        return None
    return urljoin(base_url, raw)


def is_safe_remote_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return False
    if host in _PRIVATE_HOST_MARKERS or host.endswith(".local"):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _ensure_base_tag(soup: BeautifulSoup, base_url: str | None) -> None:
    if not base_url:
        return
    head = soup.head
    if head is None:
        head = soup.new_tag("head")
        if soup.html:
            soup.html.insert(0, head)
        else:
            soup.insert(0, head)
    existing = head.find("base")
    if existing:
        existing["href"] = base_url
        return
    tag = soup.new_tag("base", href=base_url)
    head.insert(0, tag)


def _img_source(img) -> str | None:
    src = img.get("src")
    if src:
        return str(src)
    for attr in ("data-src", "data-original"):
        if img.get(attr):
            return str(img.get(attr))
    return None


def collect_preview_image_urls(html: str, base_url: str | None) -> tuple[str | None, list[str]]:
    """Return resolved base URL and unique safe image URLs to inline."""
    resolved_base = infer_base_url(html, base_url)
    soup = BeautifulSoup(html, "lxml")
    urls: list[str] = []
    seen: set[str] = set()
    for img in soup.find_all("img"):
        if len(urls) >= _MAX_INLINE_ASSETS:
            break
        absolute = resolve_resource_url(resolved_base, _img_source(img) or "")
        if not absolute or not is_safe_remote_url(absolute) or absolute in seen:
            continue
        seen.add(absolute)
        urls.append(absolute)
    return resolved_base, urls


def prepare_html_for_preview(
    html: str,
    *,
    base_url: str | None,
    fetch_asset: FetchAsset,
) -> str:
    """Rewrite img src to data URIs fetched with the page Referer, and inject <base>."""
    resolved_base = infer_base_url(html, base_url)
    soup = BeautifulSoup(html, "lxml")
    _ensure_base_tag(soup, resolved_base)

    inlined = 0
    for img in soup.find_all("img"):
        if inlined >= _MAX_INLINE_ASSETS:
            break
        absolute = resolve_resource_url(resolved_base, _img_source(img) or "")
        if not absolute or not is_safe_remote_url(absolute):
            continue
        try:
            content, content_type = fetch_asset(absolute, resolved_base)
        except Exception:
            continue
        if not content or len(content) > _MAX_ASSET_BYTES:
            continue
        mime = (content_type or "application/octet-stream").split(";")[0].strip() or "application/octet-stream"
        if not mime.startswith("image/"):
            mime = "image/jpeg"
        encoded = base64.b64encode(content).decode("ascii")
        img["src"] = f"data:{mime};base64,{encoded}"
        for attr in ("data-src", "data-original", "srcset"):
            if attr in img.attrs:
                del img.attrs[attr]
        inlined += 1

    return str(soup)
