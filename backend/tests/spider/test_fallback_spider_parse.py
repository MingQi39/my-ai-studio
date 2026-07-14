"""Fallback spider must extract non-empty titles from list pages like Douban Top250."""

from __future__ import annotations

from bs4 import BeautifulSoup

from app.spider.services.spider_pipeline_service import _fallback_spider_code

DOUBAN_LIKE_HTML = """
<html><body>
  <ol class="grid_view">
    <li>
      <div class="item">
        <div class="pic">
          <a href="https://movie.douban.com/subject/1292052/">
            <img alt="肖申克的救赎" src="poster1.jpg"/>
          </a>
        </div>
        <div class="info">
          <div class="hd">
            <a href="https://movie.douban.com/subject/1292052/">
              <span class="title">肖申克的救赎</span>
              <span class="title">&nbsp;/&nbsp;The Shawshank Redemption</span>
            </a>
          </div>
        </div>
      </div>
    </li>
    <li>
      <div class="item">
        <div class="pic">
          <a href="https://movie.douban.com/subject/1291546/">
            <img alt="霸王别姬" src="poster2.jpg"/>
          </a>
        </div>
        <div class="info">
          <div class="hd">
            <a href="https://movie.douban.com/subject/1291546/">
              <span class="title">霸王别姬</span>
            </a>
          </div>
        </div>
      </div>
    </li>
  </ol>
</body></html>
"""


def _load_parse_items(code: str):
    namespace: dict = {}
    exec(code, namespace)
    return namespace["parse_items"]


def test_fallback_spider_extracts_douban_titles_and_urls():
    code = _fallback_spider_code("https://movie.douban.com/top250", limit=5)
    parse_items = _load_parse_items(code)
    soup = BeautifulSoup(DOUBAN_LIKE_HTML, "html.parser")
    items = parse_items(soup)

    assert len(items) == 2
    assert items[0]["title"] == "肖申克的救赎"
    assert items[0]["url"] == "https://movie.douban.com/subject/1292052/"
    assert items[1]["title"] == "霸王别姬"
    assert items[1]["url"] == "https://movie.douban.com/subject/1291546/"


def test_fallback_spider_skips_empty_title_matches_when_better_selector_exists():
    """Poster-only <a> must not lock in a selector that yields empty titles."""
    code = _fallback_spider_code("https://movie.douban.com/top250", limit=5)
    parse_items = _load_parse_items(code)
    soup = BeautifulSoup(DOUBAN_LIKE_HTML, "html.parser")
    items = parse_items(soup)
    assert all(item["title"].strip() for item in items)
