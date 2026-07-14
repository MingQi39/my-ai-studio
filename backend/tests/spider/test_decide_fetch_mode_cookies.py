from app.spider.services.spider_pipeline_service import decide_initial_fetch_mode


def test_block_hard_without_cookies_stays_hard():
    anti = {"block_hard": True, "escalate_to_browser": False}
    assert decide_initial_fetch_mode(anti, http_success=True, cookies_configured=False) == "block_hard"


def test_block_hard_with_cookies_tries_playwright():
    anti = {"block_hard": True, "escalate_to_browser": False}
    assert decide_initial_fetch_mode(anti, http_success=True, cookies_configured=True) == "playwright"
