"""Tests for main chat tool handlers."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.chat_tools.handlers import calculate_handler, execute_python_handler, normalize_search_query
from app.services.chat_tools.builder import create_chat_tools_registry, adapt_response_format
from app.models.schemas import ChatToolsConfig


@pytest.mark.asyncio
async def test_calculate_handler():
    result = json.loads(await calculate_handler("(10+5)*2"))
    assert result["result"] == 30


@pytest.mark.asyncio
async def test_execute_python_handler():
    result = json.loads(await execute_python_handler("print(2 + 2)"))
    assert result["success"] is True
    assert "4" in result["stdout"]


def test_build_registry_all_tools():
    registry = create_chat_tools_registry(
        ChatToolsConfig(search=True, code=True, function=True, structured=True)
    )
    names = registry.tool_names
    assert "web_search" in names
    assert "execute_python" in names
    assert "calculate" in names
    assert "get_current_time" in names


def test_normalize_search_query_fixes_stale_year():
    now = datetime(2026, 6, 30, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert normalize_search_query("今天世界杯比分 2025", now=now) == "今天世界杯比分 2026"


def test_normalize_search_query_adds_date_when_missing_year():
    now = datetime(2026, 6, 30, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert normalize_search_query("今天世界杯比分", now=now) == "2026-06-30 今天世界杯比分"


def test_adapt_response_format_deepseek():
    schema = {"type": "json_schema", "json_schema": {"name": "x", "schema": {}}}
    assert adapt_response_format(schema, "deepseek") == {"type": "json_object"}


def test_adapt_response_format_openai_unchanged():
    schema = {"type": "json_schema", "json_schema": {"name": "x", "schema": {}}}
    assert adapt_response_format(schema, "openai") == schema


