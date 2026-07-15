"""Pipeline resume: skip stages whose artifacts already exist and validate."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.spider.services.spider_pipeline_service import spider_pipeline_stream

_ANALYSIS = json.dumps(
    {"analysis": "{}", "anti_scraping": {}, "scrape_engine": "requests", "fetch_mode": "http"}
)
_VALID_CODE = "import json\nimport requests\nfrom bs4 import BeautifulSoup\n"
_RECORDS = json.dumps([{"title": "Item One", "url": "/1"}])


class StatefulWorkspace:
    """Minimal workspace backed by an in-memory file dict that stages can mutate."""

    def __init__(self, files: dict[str, str]):
        self.files = dict(files)
        self.display_path = "/workspace"
        self.volume_name = "vol"
        self.backend = SimpleNamespace(working_dir="/workspace", execute=lambda cmd: None)

    def read_text(self, name: str) -> str | None:
        return self.files.get(name)

    def read_bytes(self, name: str) -> bytes | None:
        value = self.files.get(name)
        return value.encode("utf-8") if value is not None else None

    def exists(self, name: str) -> bool:
        return name in self.files

    def write_text(self, name: str, content: str) -> None:
        self.files[name] = content

    def list_files(self):
        return [{"name": name, "size": len(value)} for name, value in self.files.items()]


def _clean_validate_patches():
    clean_tool = MagicMock()
    clean_tool.ainvoke = AsyncMock(return_value=_RECORDS)
    validate_tool = MagicMock()
    validate_tool.ainvoke = AsyncMock(
        return_value={
            "valid": True,
            "total_records": 1,
            "valid_records": 1,
            "invalid_records": 0,
            "issues": [],
        }
    )
    return clean_tool, validate_tool


async def _run(workspace, fetch_tool, gen_mock, exec_mock, clean_tool, validate_tool):
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
        "app.spider.services.spider_pipeline_service._generate_spider_code_with_retry",
        gen_mock,
    ), patch(
        "app.spider.services.spider_pipeline_service._execute_spider_with_retry",
        exec_mock,
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
            resume=True,
        ):
            events.append(event)
    return events


@pytest.mark.asyncio
async def test_resume_runs_data_processor_only_when_data_ready():
    workspace = StatefulWorkspace(
        {
            "analysis_report.json": _ANALYSIS,
            "source_page.html": "<html/>",
            "spider.py": _VALID_CODE,
            "scraped_data.json": _RECORDS,
            "raw_data.json": _RECORDS,
            # no cleaned/validation → validated False → resume at data_processor
        }
    )
    fetch_tool = MagicMock(ainvoke=AsyncMock())
    gen_mock = AsyncMock()
    exec_mock = AsyncMock()
    clean_tool, validate_tool = _clean_validate_patches()

    events = await _run(workspace, fetch_tool, gen_mock, exec_mock, clean_tool, validate_tool)

    # Stages 1-3 skipped entirely.
    fetch_tool.ainvoke.assert_not_called()
    gen_mock.assert_not_awaited()
    exec_mock.assert_not_awaited()
    # Stage 4 ran.
    clean_tool.ainvoke.assert_awaited()
    validate_tool.ainvoke.assert_awaited()

    assert not [e for e in events if e.get("type") == "error"]
    assert any(e.get("type") == "final_response" for e in events)

    todos = [e for e in events if e.get("type") == "todos_updated"]
    first = todos[0]["todos"]
    assert [t["status"] for t in first] == ["completed", "completed", "completed", "in_progress"]


@pytest.mark.asyncio
async def test_resume_runs_execution_then_data_when_code_ready_but_no_data():
    workspace = StatefulWorkspace(
        {
            "analysis_report.json": _ANALYSIS,
            "source_page.html": "<html/>",
            "spider.py": _VALID_CODE,
            # no records yet → resume at debug_agent (execution)
        }
    )
    fetch_tool = MagicMock(ainvoke=AsyncMock())
    gen_mock = AsyncMock()

    async def exec_retry(**kwargs):
        # Simulate a successful run writing results into the workspace.
        workspace.write_text("raw_data.json", _RECORDS)
        workspace.write_text("scraped_data.json", _RECORDS)
        return {
            "success": True,
            "data_saved": True,
            "exit_code": 0,
            "record_count": 1,
            "output_preview": "saved 1 records",
        }, "resumed"

    exec_mock = AsyncMock(side_effect=exec_retry)
    clean_tool, validate_tool = _clean_validate_patches()

    events = await _run(workspace, fetch_tool, gen_mock, exec_mock, clean_tool, validate_tool)

    fetch_tool.ainvoke.assert_not_called()
    gen_mock.assert_not_awaited()
    exec_mock.assert_awaited()
    clean_tool.ainvoke.assert_awaited()

    assert not [e for e in events if e.get("type") == "error"]
    assert any(e.get("type") == "final_response" for e in events)

    todos = [e for e in events if e.get("type") == "todos_updated"]
    first = todos[0]["todos"]
    assert [t["status"] for t in first] == ["completed", "completed", "in_progress", "pending"]
