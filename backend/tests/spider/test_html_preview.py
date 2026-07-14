"""Tests for scraped HTML preview rewrite (hotlink / relative URL fix)."""

from __future__ import annotations

import base64

import pytest

from app.spider.services.html_preview import (
    infer_base_url,
    is_safe_remote_url,
    prepare_html_for_preview,
    resolve_resource_url,
)


def test_infer_base_url_from_canonical():
    html = '<html><head><link rel="canonical" href="https://movie.douban.com/subject/1/"></head></html>'
    assert infer_base_url(html, None) == "https://movie.douban.com/subject/1/"


def test_infer_base_url_prefers_meta_url():
    html = '<html><head><meta property="og:url" content="https://example.com/a"></head></html>'
    assert infer_base_url(html, "https://fallback.example/") == "https://example.com/a"


def test_infer_base_url_uses_fallback():
    assert infer_base_url("<html></html>", "https://movie.douban.com/") == "https://movie.douban.com/"


def test_infer_base_url_from_page_links_when_no_meta():
    html = """
    <html><body>
      <a href="https://img3.doubanio.com/x.jpg">cdn</a>
      <a href="https://movie.douban.com/chart">charts</a>
    </body></html>
    """
    assert infer_base_url(html, None) == "https://movie.douban.com/"


def test_resolve_relative_and_protocol_relative():
    base = "https://movie.douban.com/chart"
    assert resolve_resource_url(base, "/view/photo/x.jpg") == "https://movie.douban.com/view/photo/x.jpg"
    assert resolve_resource_url(base, "//img3.doubanio.com/a.jpg") == "https://img3.doubanio.com/a.jpg"
    assert resolve_resource_url(base, "https://img3.doubanio.com/a.jpg") == "https://img3.doubanio.com/a.jpg"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://img3.doubanio.com/a.jpg", True),
        ("http://example.com/x.png", True),
        ("ftp://example.com/x.png", False),
        ("https://127.0.0.1/x.png", False),
        ("https://localhost/x.png", False),
        ("https://192.168.1.1/x.png", False),
        ("https://10.0.0.5/x.png", False),
        ("file:///etc/passwd", False),
    ],
)
def test_is_safe_remote_url(url: str, expected: bool):
    assert is_safe_remote_url(url) is expected


def test_prepare_html_inlines_images_as_data_uri():
    html = """
    <html><head></head><body>
      <img src="https://cdn.example/poster.jpg" alt="功夫女足"/>
      <img src="/local/rel.png" alt="rel"/>
    </body></html>
    """
    fetched: list[str] = []

    def fetch_asset(url: str, referer: str | None) -> tuple[bytes, str]:
        fetched.append(url)
        assert referer == "https://movie.douban.com/"
        if url.endswith("poster.jpg"):
            return b"JPEGDATA", "image/jpeg"
        return b"PNGDATA", "image/png"

    out = prepare_html_for_preview(
        html,
        base_url="https://movie.douban.com/",
        fetch_asset=fetch_asset,
    )

    assert 'src="data:image/jpeg;base64,' in out
    assert base64.b64encode(b"JPEGDATA").decode() in out
    assert base64.b64encode(b"PNGDATA").decode() in out
    assert '<base href="https://movie.douban.com/"' in out
    assert "https://cdn.example/poster.jpg" not in out
    assert fetched == [
        "https://cdn.example/poster.jpg",
        "https://movie.douban.com/local/rel.png",
    ]


def test_prepare_html_skips_failed_assets():
    html = '<html><body><img src="https://cdn.example/missing.jpg" alt="x"/></body></html>'

    def fetch_asset(url: str, referer: str | None) -> tuple[bytes, str]:
        raise RuntimeError("418 blocked")

    out = prepare_html_for_preview(html, base_url="https://example.com/", fetch_asset=fetch_asset)
    assert 'src="https://cdn.example/missing.jpg"' in out
    assert "data:image" not in out
