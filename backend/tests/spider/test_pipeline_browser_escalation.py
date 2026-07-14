"""Pipeline browser escalation helpers and branches."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.spider.services.spider_pipeline_service import (
    _execute_spider_with_retry,
    decide_initial_fetch_mode,
    is_empty_scrape_result,
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


def test_should_retry_parse_existing_html():
    from app.spider.services.spider_pipeline_service import should_retry_parse_existing_html

    assert should_retry_parse_existing_html(
        has_source_page=True, already_retried=False
    )
    assert not should_retry_parse_existing_html(
        has_source_page=False, already_retried=False
    )
    assert not should_retry_parse_existing_html(
        has_source_page=True, already_retried=True
    )


def test_is_empty_scrape_when_saved_zero_records_nonzero_exit():
    exec_result = {
        "success": False,
        "data_saved": False,
        "exit_code": 1,
        "record_count": 0,
        "data_file": "scraped_data.json",
        "error": "2026-07-14 06:50:25,825 INFO saved 0 records",
        "output_preview": "2026-07-14 06:50:25,825 INFO saved 0 records",
    }
    detail = str(exec_result["error"])
    assert is_empty_scrape_result(exec_result, detail) is True


def test_is_empty_scrape_when_exit_zero_no_data():
    exec_result = {
        "success": False,
        "data_saved": False,
        "exit_code": 0,
        "record_count": 0,
        "data_file": "scraped_data.json",
        "error": "脚本退出码为 0，但 scraped_data.json 为空（0 条有效记录）。",
    }
    assert is_empty_scrape_result(exec_result, exec_result["error"]) is True


def test_not_empty_scrape_on_real_runtime_error():
    exec_result = {
        "success": False,
        "data_saved": False,
        "exit_code": 1,
        "record_count": 0,
        "data_file": None,
        "error": "ModuleNotFoundError: No module named 'foo'",
        "output_preview": "ModuleNotFoundError: No module named 'foo'",
    }
    assert is_empty_scrape_result(exec_result, exec_result["error"]) is False


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
async def test_pipeline_empty_scrape_retries_from_existing_source_page():
    """When playwright already ran and scrape is empty, re-analyze local HTML once."""
    html = "<html><body><a href='/1'>Item One</a></body></html>"
    workspace = SimpleNamespace(
        write_text=lambda *a, **k: None,
        read_text=lambda name: html if name == "source_page.html" else None,
        read_bytes=lambda name: b'[{"title":"Item One","url":"/1"}]' if name.endswith(".json") else b"",
        exists=lambda name: name in {"source_page.html", "scraped_data.json", "raw_data.json"},
        list_files=lambda: [{"name": "source_page.html", "size": 10}],
        display_path="/workspace",
        volume_name="vol",
        backend=SimpleNamespace(working_dir="/workspace", execute=lambda cmd: None),
    )

    empty = {
        "success": False,
        "data_saved": False,
        "exit_code": 1,
        "record_count": 0,
        "error": "saved 0 records",
        "output_preview": "saved 0 records",
    }
    ok = {
        "success": True,
        "data_saved": True,
        "exit_code": 0,
        "record_count": 1,
        "output_preview": "saved 1 records",
    }
    exec_calls = {"n": 0}

    async def execute_retry(**kwargs):
        exec_calls["n"] += 1
        if exec_calls["n"] == 1:
            return empty, "template"
        return ok, "template"

    analyze_calls: list[dict] = []
    analyze_tool = MagicMock()

    async def analyze_ainvoke(payload):
        analyze_calls.append(payload)
        return {"title": "t", "links_count": 1}

    analyze_tool.ainvoke = analyze_ainvoke

    gen_calls = {"n": 0}

    async def gen_code(**kwargs):
        gen_calls["n"] += 1
        return "print('x')\n", "template"

    save_tool = MagicMock()
    save_tool.ainvoke = AsyncMock(return_value="saved")

    clean_tool = MagicMock()
    clean_tool.ainvoke = AsyncMock(return_value='[{"title":"Item One","url":"/1"}]')
    validate_tool = MagicMock()
    validate_tool.ainvoke = AsyncMock(
        return_value={"valid": True, "total_records": 1, "valid_records": 1, "invalid_records": 0, "issues": []}
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
        MagicMock(
            ainvoke=AsyncMock(
                return_value={
                    "success": True,
                    "html_content": html,
                    "html_file": "source_page.html",
                    "status_code": 200,
                }
            )
        ),
    ), patch(
        "app.spider.services.spider_pipeline_service.decide_initial_fetch_mode",
        return_value="http",
    ), patch(
        "app.spider.services.spider_pipeline_service.classify_fetch_result",
        return_value={
            "level": "none",
            "block_hard": False,
            "escalate_to_browser": False,
            "success": True,
        },
    ), patch(
        "app.spider.services.spider_pipeline_service.analyze_html_structure",
        analyze_tool,
    ), patch(
        "app.spider.services.spider_pipeline_service._generate_spider_code_with_retry",
        new=AsyncMock(side_effect=gen_code),
    ), patch(
        "app.spider.services.spider_pipeline_service._validate_python_code",
        new=AsyncMock(return_value={"valid": True}),
    ), patch(
        "app.spider.services.spider_pipeline_service.save_spider_code",
        save_tool,
    ), patch(
        "app.spider.services.spider_pipeline_service._execute_spider_with_retry",
        new=AsyncMock(side_effect=execute_retry),
    ), patch(
        "app.spider.services.spider_pipeline_service.clean_data",
        clean_tool,
    ), patch(
        "app.spider.services.spider_pipeline_service.validate_data",
        validate_tool,
    ):
        async for event in spider_pipeline_stream(
            message="爬 https://example.com/list",
            conversation_history=[],
            user_id="u",
            session_id="s",
            llm_api_key="k",
            llm_base_url="http://x",
            model_name="m",
            target_url="https://example.com/list",
        ):
            events.append(event)

    assert exec_calls["n"] == 2
    assert gen_calls["n"] == 2
    assert any(c.get("html_file") == "source_page.html" for c in analyze_calls)
    errors = [e for e in events if e.get("type") == "error"]
    assert not errors
    assert any(e.get("type") == "done" for e in events)


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
