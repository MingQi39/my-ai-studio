"""Classify fetch results for spider anti-scrape handling."""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

_TEXT_THRESHOLD = 500
_CF_CHALLENGE_TOKENS = ("just a moment", "checking your browser", "cf-challenge", "attention required")
_CAPTCHA_TOKENS = ("captcha", "recaptcha", "验证码", "hcaptcha")
_VISITOR_WALL_TOKENS = (
    "sina visitor system",
    "visitor system",
    "/visitor/visitor",
    "passport.weibo.com/visitor",
    "请先登录",
    "login required",
)

_ERROR_HINTS: dict[str, list[str]] = {
    "fetch_failed": [
        "检查目标网址是否可在浏览器正常打开",
        "确认本机网络可访问该域名",
        "若需 JS 渲染，将 SPIDER_DOCKER_IMAGE 换为 Playwright 镜像后重试",
    ],
    "anti_scrape_hard": [
        "目标页需要人工验证或登录态：可在目标网址下方粘贴登录 Cookie（不做自动绕过）",
        "请换更开放的公开列表页，或稍后再试",
    ],
    "browser_image_unavailable": [
        "将 SPIDER_DOCKER_IMAGE 设为 mcr.microsoft.com/playwright/python:v1.61.0-jammy（或等价镜像）",
        "docker pull 该镜像后重启后端，并建议 SPIDER_DOCKER_MEMORY_LIMIT≥2g",
        "新会话会创建新容器；旧会话容器仍指向旧镜像时请新开会话",
    ],
    "browser_fetch_failed": [
        "浏览器沙箱抓取失败，检查目标站是否可访问",
        "适当增大超时后重试，或换静态列表页",
        "若 Chromium 在 page.content 崩溃：确认 SPIDER_DOCKER_SHM_SIZE≥1g、MEMORY≥2g，并新开会话重建容器",
    ],
    "empty_scrape": [
        "把目标网址换成明确的列表页",
        "打开工作区 source_page.html / spider.py，核对选择器",
        "若页面强依赖登录或验证码，当前流水线无法完成",
    ],
    "execution_failed": [
        "查看沙箱运行输出定位异常",
        "小模型生成不稳时可换官方 API 模型",
    ],
}

_ANTI_SCRAPE_HARD_WITH_COOKIES = [
    "已注入 Cookie 仍被拦截：Cookie 可能过期或无效，请更新后重试",
    "请换更开放的公开列表页；当前不支持自动绕过人机验证",
]


def classify_fetch_result(
    *,
    url: str,
    html: str = "",
    status_code: int | None = None,
) -> dict[str, Any]:
    content = html or ""
    lowered = content.lower()
    mechanisms: list[str] = []
    recommendations: list[str] = []

    url_lower = (url or "").lower()
    haystack = f"{lowered}\n{url_lower}"
    if any(t in haystack for t in _VISITOR_WALL_TOKENS):
        return {
            "url": url,
            "level": "hard",
            "detected_mechanisms": ["Login/Visitor Wall"],
            "recommendations": ["需要登录态或换公开列表页；当前不自动绕过"],
            "escalate_to_browser": False,
            "block_hard": True,
            "has_anti_scraping": True,
            "success": True,
            "status_code": status_code,
        }

    soup = BeautifulSoup(content, "lxml") if content else None
    visible = (soup.get_text(" ", strip=True) if soup else content).lower()

    # CAPTCHA tokens frequently appear in bundled JS; only visible text counts as hard.
    has_captcha = any(t in visible for t in _CAPTCHA_TOKENS)
    if has_captcha:
        mechanisms.append("CAPTCHA")
        recommendations.append("需要人工验证；当前不自动绕过")
        return {
            "url": url,
            "level": "hard",
            "detected_mechanisms": mechanisms,
            "recommendations": recommendations,
            "escalate_to_browser": False,
            "block_hard": True,
            "has_anti_scraping": True,
            "success": True,
            "status_code": status_code,
        }

    cf = "cloudflare" in lowered
    cf_challenge = cf and any(t in lowered for t in _CF_CHALLENGE_TOKENS)
    if cf:
        mechanisms.append("Cloudflare")

    visible_len = len(visible.strip()) if visible else 0
    script_heavy = bool(soup and soup.find_all("script") and visible_len < _TEXT_THRESHOLD)
    if script_heavy:
        mechanisms.append("JavaScript Rendering")
        recommendations.append("使用沙箱内 Playwright 渲染后再解析")

    if cf_challenge or script_heavy:
        return {
            "url": url,
            "level": "js_render",
            "detected_mechanisms": mechanisms,
            "recommendations": recommendations or ["使用 Playwright"],
            "escalate_to_browser": True,
            "block_hard": False,
            "has_anti_scraping": True,
            "success": True,
            "status_code": status_code,
        }

    soft_status = status_code in {401, 403, 429, 503}
    if soft_status:
        mechanisms.append(f"HTTP {status_code}")
        recommendations.extend(["稍后重试", "必要时升级 Playwright 再抓一次"])
        return {
            "url": url,
            "level": "soft",
            "detected_mechanisms": mechanisms,
            "recommendations": recommendations,
            "escalate_to_browser": False,
            "block_hard": False,
            "has_anti_scraping": True,
            "success": True,
            "status_code": status_code,
        }

    if not recommendations:
        recommendations = [
            "添加随机延迟 (1-3秒)",
            "使用随机 User-Agent",
            "设置合理的请求头",
        ]

    return {
        "url": url,
        "level": "none",
        "detected_mechanisms": mechanisms,
        "recommendations": recommendations,
        "escalate_to_browser": False,
        "block_hard": False,
        "has_anti_scraping": len(mechanisms) > 0,
        "success": True,
        "status_code": status_code,
    }


def hints_for_error_code(code: str, *, cookies_configured: bool = False) -> list[str]:
    if code == "anti_scrape_hard" and cookies_configured:
        return list(_ANTI_SCRAPE_HARD_WITH_COOKIES)
    return list(
        _ERROR_HINTS.get(code)
        or [
            "检查目标网址与网络",
            "查看会话工作区日志后重试",
        ]
    )
