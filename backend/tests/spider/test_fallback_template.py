"""Builtin spider template + fallback observability."""

from __future__ import annotations

import ast
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from bs4 import BeautifulSoup

from app.spider.services.spider_pipeline_service import (
    _execute_spider_with_retry,
    _fallback_spider_code,
)
from app.spider.services.tools import validate_data


DOUBAN_ITEM_HTML = """
<html><body>
<div class="grid-view">
  <div class="item">
    <div class="pic">
      <a href="https://movie.douban.com/subject/1292052/">
        <img alt="肖申克的救赎" src="poster.jpg"/>
      </a>
    </div>
    <div class="info">
      <div class="hd">
        <a href="https://movie.douban.com/subject/1292052/">
          <span class="title">肖申克的救赎</span>
          <span class="title">&nbsp;/&nbsp;The Shawshank Redemption</span>
        </a>
      </div>
    </div>
  </div>
</div>
</body></html>
"""


def _load_parse_items(code: str):
    module = ast.parse(code)
    ns: dict = {}
    exec(compile(module, "<fallback>", "exec"), ns)
    return ns["parse_items"]


def test_fallback_template_extracts_douban_movie_title():
    code = _fallback_spider_code("https://movie.douban.com/top250", limit=5)
    parse_items = _load_parse_items(code)
    items = parse_items(BeautifulSoup(DOUBAN_ITEM_HTML, "lxml"))
    assert len(items) == 1
    assert items[0]["title"] == "肖申克的救赎"
    assert "1292052" in items[0]["url"]


@pytest.mark.asyncio
async def test_validate_data_requires_title_when_requested():
    cleaned = '[{"url": "https://movie.douban.com/subject/1292052/"}]'
    result = await validate_data.ainvoke({"data": cleaned, "required_fields": ["title"]})
    assert result["valid"] is False
    assert result["invalid_records"] == 1


@pytest.mark.asyncio
async def test_validate_data_passes_with_title_and_url():
    cleaned = '[{"title": "肖申克的救赎", "url": "https://movie.douban.com/subject/1292052/"}]'
    result = await validate_data.ainvoke({"data": cleaned, "required_fields": ["title"]})
    assert result["valid"] is True
    assert result["valid_records"] == 1


@pytest.mark.asyncio
async def test_execute_retry_attaches_original_error_when_falling_back_to_template():
    workspace = SimpleNamespace(
        read_text=lambda name: "print('llm-broken')\n",
    )
    llm_fail = {
        "success": False,
        "error": "AttributeError: 'CaseInsensitiveDict' object has no attribute 'add'",
        "exit_code": 1,
        "data_saved": False,
    }
    template_ok = {
        "success": True,
        "output_preview": "saved 5 records\n",
        "exit_code": 0,
        "data_saved": True,
        "record_count": 5,
    }
    execute = AsyncMock()
    execute.ainvoke = AsyncMock(side_effect=[llm_fail, template_ok])

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.spider.services.spider_pipeline_service._fix_runtime_spider_code",
            AsyncMock(return_value="still broken {{{"),
        )
        mp.setattr(
            "app.spider.services.spider_pipeline_service._validate_python_code",
            AsyncMock(return_value={"valid": False}),
        )
        mp.setattr(
            "app.spider.services.spider_pipeline_service.save_spider_code",
            SimpleNamespace(ainvoke=AsyncMock(return_value="ok")),
        )
        result, source = await _execute_spider_with_retry(
            execute_in_sandbox=execute,
            workspace=workspace,
            llm_api_key="k",
            llm_base_url="http://localhost",
            model_name="m",
            target_url="https://movie.douban.com/top250",
            code_source="llm",
        )

    assert source == "template"
    assert result["success"] is True
    assert "AttributeError" in str(result.get("fallback_from_error") or "")
