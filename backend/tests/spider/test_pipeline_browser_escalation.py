"""Pipeline browser escalation helpers and branches."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.spider.services.spider_pipeline_service import (
    _execute_spider_with_retry,
    decide_initial_fetch_mode,
    should_escalate_after_empty_scrape,
    spider_pipeline_stream,
)


def test_decide_block_hard():
    assert decide_initial_fetch_mode({"block_hard": True}, http_success=True) == "block_hard"


def test_decide_escalate_js_render():
    assert (
        decide_initial_fetch_mode({"escalate_to_browser": True, "block_hard": False}, http_success=True)
        == "playwright"
    )


def test_decide_http_fail_escalates():
    assert (
        decide_initial_fetch_mode({"block_hard": False, "escalate_to_browser": False}, http_success=False)
        == "playwright"
    )


def test_decide_http_ok_none():
    assert (
        decide_initial_fetch_mode(
            {"block_hard": False, "escalate_to_browser": False, "level": "none"},
            http_success=True,
        )
        == "http"
    )


def test_should_escalate_after_empty_scrape():
    assert should_escalate_after_empty_scrape(
        scrape_engine="requests", anti_level="soft", already_escalated=False
    )
    assert not should_escalate_after_empty_scrape(
        scrape_engine="requests", anti_level="none", already_escalated=False
    )
    assert not should_escalate_after_empty_scrape(
        scrape_engine="playwright", anti_level="soft", already_escalated=False
    )
    assert not should_escalate_after_empty_scrape(
        scrape_engine="requests", anti_level="soft", already_escalated=True
    )
    assert should_escalate_after_empty_scrape(
        scrape_engine="requests", anti_level="js_render", already_escalated=False
    )


@pytest.mark.asyncio
async def test_execute_retry_playwright_engine_does_not_fall_back_to_requests():
    workspace = SimpleNamespace(
        read_text=lambda name: "print('x')\n",
        write_text=lambda *a, **k: None,
    )
    llm_fail = {"success": False, "error": "boom", "exit_code": 1, "data_saved": False}
    template_ok = {
        "success": True,
        "exit_code": 0,
        "data_saved": True,
        "record_count": 1,
        "output_preview": "ok",
    }
    calls: list[str] = []

    execute_in_sandbox = SimpleNamespace()

    async def ainvoke(payload):
        code = payload["code"]
        calls.append(code)
        if "sync_playwright" in code:
            return template_ok
        return llm_fail

    execute_in_sandbox.ainvoke = ainvoke

    save_tool = MagicMock()
    save_tool.ainvoke = AsyncMock(return_value="saved")

    with patch(
        "app.spider.services.spider_pipeline_service._fix_runtime_spider_code",
        new=AsyncMock(return_value="print('still-broken')\n"),
    ), patch(
        "app.spider.services.spider_pipeline_service._validate_python_code",
        new=AsyncMock(return_value={"valid": True}),
    ), patch(
        "app.spider.services.spider_pipeline_service.save_spider_code",
        save_tool,
    ):
        result, source = await _execute_spider_with_retry(
            execute_in_sandbox=execute_in_sandbox,
            workspace=workspace,
            llm_api_key="k",
            llm_base_url="http://x",
            model_name="m",
            target_url="https://example.com",
            code_source="llm",
            scrape_engine="playwright",
        )

    assert source == "template"
    assert result["success"] is True
    assert any("sync_playwright" in c for c in calls)


@pytest.mark.asyncio
async def test_pipeline_js_render_probe_false_emits_browser_image_unavailable():
    scripts = "".join(f"<script>var x{i}=1;</script>" for i in range(20))
    html = f"<html><body>{scripts}<div></div></body></html>"

    workspace = SimpleNamespace(
        write_text=lambda *a, **k: None,
        read_text=lambda *a, **k: None,
        list_files=lambda: [],
        display_path="/workspace",
        backend=SimpleNamespace(working_dir="/workspace", execute=lambda cmd: None),
    )

    fetch_tool = MagicMock()
    fetch_tool.ainvoke = AsyncMock(
        return_value={
            "success": True,
            "html_content": html,
            "html_file": "source_page.html",
            "status_code": 200,
        }
    )

    events = []
    with patch(
        "app.spider.services.spider_pipeline_service.initialize_session_sandbox",
        return_value=workspace,
    ), patch(
        "app.spider.services.spider_pipeline_service.set_sandbox_workspace",
    ), patch(
        "app.spider.services.spider_pipeline_service.create_execute_in_sandbox_tool",
        return_value=SimpleNamespace(),
    ), patch(
        "app.spider.services.spider_pipeline_service.fetch_url",
        fetch_tool,
    ), patch(
        "app.spider.services.spider_pipeline_service.probe_playwright_available",
        return_value=False,
    ):
        async for event in spider_pipeline_stream(
            message="爬 https://spa.example/",
            conversation_history=[],
            user_id="u",
            session_id="s",
            llm_api_key="k",
            llm_base_url="http://x",
            model_name="m",
            target_url="https://spa.example/",
        ):
            events.append(event)

    errors = [e for e in events if e.get("type") == "error"]
    assert errors
    assert errors[0]["code"] == "browser_image_unavailable"
