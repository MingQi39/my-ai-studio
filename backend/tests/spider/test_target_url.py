from app.spider.services.target_url import try_resolve_spider_target_url


def test_prefers_explicit_target_url():
    assert (
        try_resolve_spider_target_url("随便说说", "https://movie.douban.com/top250")
        == "https://movie.douban.com/top250"
    )


def test_extracts_url_from_message():
    assert (
        try_resolve_spider_target_url(
            "分析 https://movie.douban.com/top250 并爬取标题", None
        )
        == "https://movie.douban.com/top250"
    )


def test_strips_trailing_punctuation():
    assert (
        try_resolve_spider_target_url("看这个 https://example.com/list).", None)
        == "https://example.com/list"
    )


def test_returns_none_when_missing():
    assert try_resolve_spider_target_url("帮我解释一下上次的代码", None) is None
    assert try_resolve_spider_target_url("hello", "   ") is None
