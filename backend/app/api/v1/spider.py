"""Spider Agent API endpoints."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Literal
from uuid import UUID

import mimetypes

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user_auth, get_db, get_model_service, get_session_service
from app.models.database import SessionType
from app.spider.schemas import SpiderAgentRequest, SpiderWorkspaceFile, SpiderWorkspaceResponse
from app.spider.services.chat_persistence import (
    messages_to_history,
    resolve_spider_session,
    save_spider_assistant_message,
    save_spider_user_message,
)
from app.spider.services.sandbox import initialize_session_sandbox, list_workspace_files
from app.spider.services.spider_agent_service import spider_agent_stream
from app.spider.services.todo_events import normalize_todos
from app.travel.llm_context import resolve_travel_llm

router = APIRouter(prefix="/spider", tags=["spider"])


class _SSESessionEvent(BaseModel):
    type: Literal["session"] = "session"
    session_id: str
    created: bool


def _json_dumps_sse(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False, default=str)


async def format_sse_stream(stream: AsyncIterator[dict]) -> AsyncIterator[str]:
    async for event in stream:
        yield f"data: {_json_dumps_sse(event)}\n\n"
        await asyncio.sleep(0)


async def _persist_spider_stream(
    stream: AsyncIterator[dict[str, Any]],
    session_service,
    session_id: UUID,
) -> AsyncIterator[dict[str, Any]]:
    content_buffer = ""
    tool_trace: list[dict[str, Any]] = []
    pending: dict[str, dict[str, Any]] = {}
    has_error = False
    failure: dict[str, Any] | None = None
    latest_todos: list[dict[str, Any]] | None = None

    async for event in stream:
        yield event

        etype = event.get("type")
        if etype == "chunk" and event.get("content"):
            content_buffer += event["content"]
        if etype == "final_response" and event.get("content"):
            content_buffer = event["content"]

        if etype == "tool_call_start":
            call_id = str(event.get("call_id") or "")
            if not call_id:
                continue
            pending[call_id] = {
                "id": call_id,
                "tool_name": event.get("tool_name") or event.get("raw_tool_name") or "unknown",
                "tool_args": event.get("tool_args") or {},
                "status": "pending",
            }
            if event.get("raw_tool_name"):
                pending[call_id]["raw_tool_name"] = event.get("raw_tool_name")

        if etype == "tool_call_result":
            call_id = str(event.get("call_id") or "")
            if not call_id:
                continue
            entry = pending.get(call_id)
            if entry is None:
                continue
            entry["result"] = event.get("result")
            entry["status"] = event.get("status") or ("error" if event.get("error") else "success")
            tool_trace.append(entry)

        if etype == "todos_updated":
            normalized = normalize_todos(event.get("todos"))
            if normalized:
                latest_todos = normalized

        if etype == "error":
            has_error = True
            if event.get("message"):
                content_buffer = str(event["message"])
            failure = {
                "code": event.get("code"),
                "title": event.get("title") or "任务执行失败",
                "detail": event.get("detail") or event.get("message") or "",
                "hints": event.get("hints") or [],
                "stage": event.get("stage"),
                "recoverable": bool(event.get("recoverable")),
            }

    if not content_buffer and not tool_trace and not failure and not latest_todos:
        return

    if has_error and not content_buffer:
        content_buffer = "任务执行失败"
    elif not content_buffer:
        content_buffer = "（无回复内容）"

    await save_spider_assistant_message(
        session_service=session_service,
        session_id=session_id,
        content=content_buffer,
        tool_trace=tool_trace if tool_trace else None,
        failure=failure,
        todos=latest_todos,
    )


@router.post("/agent/run")
async def spider_agent_run(
    request: SpiderAgentRequest,
    user_id: UUID = Depends(get_current_user_auth),
    model_service=Depends(get_model_service),
    session_service=Depends(get_session_service),
    db: AsyncSession = Depends(get_db),
):
    del db

    try:
        session_id, created = await resolve_spider_session(
            session_service=session_service,
            user_id=user_id,
            session_id=request.session_id,
            first_message=request.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    stored_messages = await session_service.get_messages(session_id)
    conversation_history = messages_to_history(stored_messages)

    await save_spider_user_message(
        session_service=session_service,
        session_id=session_id,
        content=request.message,
        target_url=request.target_url,
    )

    ctx = await resolve_travel_llm(model_service, user_id, request.model_config_id)

    async def event_stream() -> AsyncIterator[dict[str, Any]]:
        yield {"type": "session", "session_id": str(session_id), "created": created}
        inner = spider_agent_stream(
            message=request.message,
            conversation_history=conversation_history,
            user_id=str(user_id),
            session_id=str(session_id),
            llm_api_key=ctx.api_key,
            llm_base_url=ctx.base_url,
            model_name=ctx.model_id,
            target_url=request.target_url,
        )
        async for event in _persist_spider_stream(inner, session_service, session_id):
            yield event

    return StreamingResponse(
        format_sse_stream(event_stream()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/workspace/{session_id}", response_model=SpiderWorkspaceResponse)
async def spider_workspace(
    session_id: UUID,
    user_id: UUID = Depends(get_current_user_auth),
    session_service=Depends(get_session_service),
):
    session = await session_service.get_session(session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.session_type != SessionType.spider:
        raise HTTPException(status_code=400, detail="Not a spider session")

    try:
        workspace = initialize_session_sandbox(str(user_id), str(session_id))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Docker sandbox unavailable: {exc}") from exc

    files = [SpiderWorkspaceFile(**item) for item in list_workspace_files(workspace)]
    return SpiderWorkspaceResponse(
        session_id=str(session_id),
        workspace_path=workspace.display_path,
        volume_name=workspace.volume_name,
        files=files,
    )


def _validate_workspace_filename(filename: str) -> str:
    name = filename.strip()
    if not name or name in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return name


@router.get("/workspace/{session_id}/files/{filename}")
async def spider_workspace_file(
    session_id: UUID,
    filename: str,
    user_id: UUID = Depends(get_current_user_auth),
    session_service=Depends(get_session_service),
):
    safe_name = _validate_workspace_filename(filename)

    session = await session_service.get_session(session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.session_type != SessionType.spider:
        raise HTTPException(status_code=400, detail="Not a spider session")

    try:
        workspace = initialize_session_sandbox(str(user_id), str(session_id))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Docker sandbox unavailable: {exc}") from exc

    if not workspace.exists(safe_name):
        raise HTTPException(status_code=404, detail="File not found")

    content = workspace.read_bytes(safe_name)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")

    media_type, _ = mimetypes.guess_type(safe_name)
    return Response(content=content, media_type=media_type or "application/octet-stream")
