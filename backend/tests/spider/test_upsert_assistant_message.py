from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.spider.services.chat_persistence import upsert_spider_assistant_message


@pytest.mark.asyncio
async def test_upsert_creates_when_message_id_none():
    session_id = uuid4()
    created_id = uuid4()
    session_service = MagicMock()
    msg = MagicMock()
    msg.id = str(created_id)
    session_service.add_message = AsyncMock(return_value=msg)
    session_service.update_message = AsyncMock()

    result = await upsert_spider_assistant_message(
        session_service=session_service,
        session_id=session_id,
        message_id=None,
        content="",
        tool_trace=[{"id": "c1", "tool_name": "task", "status": "pending"}],
        is_complete=False,
    )

    assert result == created_id
    session_service.add_message.assert_awaited_once()
    data = session_service.add_message.await_args.args[1]
    assert data.is_complete is False
    assert data.content == ""
    assert data.tool_calls[0]["tool_trace"][0]["status"] == "pending"
    session_service.update_message.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_updates_existing_message():
    session_id = uuid4()
    message_id = uuid4()
    session_service = MagicMock()
    session_service.add_message = AsyncMock()
    session_service.update_message = AsyncMock(return_value=MagicMock())

    result = await upsert_spider_assistant_message(
        session_service=session_service,
        session_id=session_id,
        message_id=message_id,
        content="你好",
        tool_trace=[{"id": "c1", "tool_name": "task", "status": "success", "result": "ok"}],
        todos=[{"content": "分析", "status": "completed"}],
        is_complete=True,
    )

    assert result == message_id
    session_service.update_message.assert_awaited_once()
    call_kwargs = session_service.update_message.await_args.kwargs
    assert call_kwargs["content"] == "你好"
    assert call_kwargs["is_complete"] is True
    assert call_kwargs["tool_calls"][0]["todos"][0]["content"] == "分析"
    session_service.add_message.assert_not_called()
