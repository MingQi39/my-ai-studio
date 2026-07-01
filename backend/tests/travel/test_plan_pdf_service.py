import pytest

from app.travel.services.plan_pdf_service import (
    render_markdown_pdf,
    sanitize_pdf_filename,
    _format_inline_text,
)


SAMPLE_MARKDOWN = """# 成都美食之旅

> 导出时间：2026-06-30 17:17

## 行程概览

- **目的地**：成都
- **天数**：3 天

## 预算明细

| 类别 | 金额 | 说明 |
| --- | ---: | --- |
| 餐饮 | 1200 CNY | 火锅与小吃 |
"""


def test_sanitize_pdf_filename():
    assert sanitize_pdf_filename("成都美食之旅") == "成都美食之旅"
    assert sanitize_pdf_filename('bad/name:test') == "bad-name-test"


def test_format_inline_text():
    assert _format_inline_text("**目的地**：成都") == "目的地：成都"
    assert _format_inline_text("[高德导航](https://example.com)") == "高德导航"
    assert _format_inline_text("📍 春熙路") == "地点： 春熙路"


def test_render_markdown_pdf_produces_bytes():
    pdf = render_markdown_pdf(SAMPLE_MARKDOWN, "成都美食之旅")
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000

    from io import BytesIO

    from pypdf import PdfReader

    text = PdfReader(BytesIO(pdf)).pages[0].extract_text() or ""
    assert "成都" in text
    assert "目的地" in text


def test_render_markdown_pdf_does_not_one_line_per_page():
    lines = ["## 每日行程", ""]
    for index in range(20):
        lines.extend(
            [
                f"### Day {index + 1}",
                "",
                f"- **上午** 活动 {index + 1}",
                f"  - 描述 {index + 1}",
                f"  - 📍 地点 {index + 1}",
                f"  - [高德导航](https://example.com/{index})",
            ]
        )
    markdown = "\n".join(lines)
    pdf = render_markdown_pdf(markdown, "测试")
    from io import BytesIO

    from pypdf import PdfReader

    page_count = len(PdfReader(BytesIO(pdf)).pages)
    assert page_count <= 4
