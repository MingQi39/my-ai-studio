from app.spider.services.runtime_route import choose_spider_runtime


def test_with_url_uses_pipeline():
    assert choose_spider_runtime("爬取", "https://example.com") == "pipeline"
    assert choose_spider_runtime("看 https://example.com/a", None) == "pipeline"


def test_without_url_uses_deepagent():
    assert choose_spider_runtime("解释上次清洗结果", None) == "deepagent"
