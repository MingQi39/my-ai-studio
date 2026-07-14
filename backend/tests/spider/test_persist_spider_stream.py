import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.api.v1.spider import _persist_spider_stream


async def _collect(agen):
    return [item async for item in agen]


@pytest.mark.asyncio
async def test_persist_checkpoints_on_tool_start_and_finalizes():
    session_id = uuid4()
    message_id = uuid4()
    session_service = AsyncMock()
    upsert = AsyncMock(return_value=message_id)

    async def fake_stream():
        yield {
            "type": "tool_call_start",
            "call_id": "c1",
            "tool_name": "task",
            "raw_tool_name": "task",
            "tool_args": {"subagent_type": "code_generator"},
        }
        yield {
            "type": "tool_call_result",
            "call_id": "c1",
            "result": "ok",
            "status": "success",
        }
        yield {"type": "final_response", "content": "完成"}
        yield {"type": "done"}

    with patch("app.api.v1.spider.upsert_spider_assistant_message", upsert):
        events = await _collect(_persist_spider_stream(fake_stream(), session_service, session_id))

    assert any(e.get("type") == "tool_call_start" for e in events)
    assert upsert.await_count >= 2
    last_call = upsert.await_args_list[-1]
    assert last_call.kwargs["is_complete"] is True
    assert last_call.kwargs["content"] == "完成"
    trace = last_call.kwargs["tool_trace"]
    assert len(trace) == 1
    assert trace[0]["status"] == "success"


@pytest.mark.asyncio
async def test_persist_flush_incomplete_on_cancel():
    session_id = uuid4()
    message_id = uuid4()
    session_service = AsyncMock()
    upsert = AsyncMock(return_value=message_id)

    async def fake_stream():
        yield {
            "type": "tool_call_start",
            "call_id": "c1",
            "tool_name": "task",
            "tool_args": {},
        }
        raise asyncio.CancelledError()

    with patch("app.api.v1.spider.upsert_spider_assistant_message", upsert):
        with pytest.raises(asyncio.CancelledError):
            await _collect(_persist_spider_stream(fake_stream(), session_service, session_id))

    assert upsert.await_count >= 1
    last = upsert.await_args_list[-1]
    assert last.kwargs["is_complete"] is False
    assert last.kwargs["tool_trace"][0]["status"] == "pending"
