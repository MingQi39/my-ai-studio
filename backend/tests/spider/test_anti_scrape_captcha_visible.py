"""Captcha heuristic should not hard-block on hidden script/comment tokens."""

from app.spider.services.anti_scrape import classify_fetch_result


def test_captcha_token_only_in_script_is_not_hard():
    scripts = "".join(
        f"<script>window.__cfg_{i}={{module:'captcha-sdk'}};</script>" for i in range(20)
    )
    html = f"<html><head><title>微博</title></head><body>{scripts}<div id='app'></div></body></html>"
    result = classify_fetch_result(url="https://www.weibo.com/", html=html, status_code=200)
    assert result["level"] != "hard"
    assert result["block_hard"] is False
    assert result["escalate_to_browser"] is True


def test_visible_captcha_text_still_hard():
    html = "<html><body><h1>请完成验证码</h1><div class='captcha'></div></body></html>"
    result = classify_fetch_result(url="https://www.weibo.com/", html=html, status_code=200)
    assert result["level"] == "hard"
    assert result["block_hard"] is True
    assert "CAPTCHA" in result["detected_mechanisms"]
