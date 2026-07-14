import pytest

from app.spider.services.anti_scrape import classify_fetch_result, hints_for_error_code


def test_classify_plain_list_html_is_none():
    html = "<html><body><div class='item'><span class='title'>A</span><a href='/1'>x</a></div></body></html>"
    result = classify_fetch_result(url="https://example.com/list", html=html, status_code=200)
    assert result["level"] == "none"
    assert result["escalate_to_browser"] is False
    assert result["block_hard"] is False


def test_classify_script_shell_is_js_render():
    scripts = "".join(f"<script>var x{i}=1;</script>" for i in range(20))
    html = f"<html><body>{scripts}<div></div></body></html>"
    result = classify_fetch_result(url="https://spa.example/", html=html, status_code=200)
    assert result["level"] == "js_render"
    assert result["escalate_to_browser"] is True
    assert "JavaScript Rendering" in result["detected_mechanisms"]


def test_classify_captcha_is_hard():
    html = "<html><body><div>请完成验证码 captcha</div></body></html>"
    result = classify_fetch_result(url="https://example.com/", html=html, status_code=200)
    assert result["level"] == "hard"
    assert result["block_hard"] is True
    assert result["escalate_to_browser"] is False


def test_classify_cloudflare_challenge_escalates():
    html = "<html><body>cloudflare just a moment checking your browser</body></html>"
    result = classify_fetch_result(url="https://example.com/", html=html, status_code=403)
    assert result["level"] == "js_render"
    assert result["escalate_to_browser"] is True


def test_classify_403_without_captcha_is_soft():
    result = classify_fetch_result(
        url="https://example.com/",
        html="<html><body>Forbidden</body></html>",
        status_code=403,
    )
    assert result["level"] == "soft"
    assert result["block_hard"] is False


def test_hints_for_known_codes():
    hints = hints_for_error_code("browser_image_unavailable")
    assert any(("镜像" in h) or ("Playwright" in h) or ("playwright" in h) for h in hints)
    assert hints_for_error_code("anti_scrape_hard")
    assert hints_for_error_code("unknown_xyz")


@pytest.mark.asyncio
async def test_detect_anti_scraping_returns_level_fields():
    from app.spider.services.tools import detect_anti_scraping

    html = "<html><body>请完成验证码 captcha</body></html>"
    result = await detect_anti_scraping.ainvoke({"url": "https://x.test", "html": html})
    assert result["success"] is True
    assert result["level"] == "hard"
    assert result["block_hard"] is True
    assert "has_anti_scraping" in result


def test_classify_sina_visitor_system_is_hard():
    html = (
        "<!DOCTYPE html><html><head><title>Sina Visitor System</title></head>"
        "<body><span id='message'></span>"
        "<script src='/js/visitor/mini_original.js'></script></body></html>"
    )
    result = classify_fetch_result(
        url="https://www.weibo.com/",
        html=html,
        status_code=200,
    )
    assert result["level"] == "hard"
    assert result["block_hard"] is True
    assert result["escalate_to_browser"] is False
    assert "Login/Visitor Wall" in result["detected_mechanisms"]


def test_classify_visitor_url_is_hard_even_with_scripts():
    scripts = "".join(f"<script>var x{i}=1;</script>" for i in range(20))
    html = f"<html><body>{scripts}<div>loading</div></body></html>"
    result = classify_fetch_result(
        url="https://passport.weibo.com/visitor/visitor?entry=miniblog&a=enter&url=https://www.weibo.com/",
        html=html,
        status_code=200,
    )
    assert result["level"] == "hard"
    assert result["block_hard"] is True
    assert result["escalate_to_browser"] is False


def test_anti_scrape_hard_hints_mention_login_or_public_list():
    hints = hints_for_error_code("anti_scrape_hard")
    joined = " ".join(hints)
    assert ("登录" in joined) or ("Cookie" in joined) or ("公开" in joined)
