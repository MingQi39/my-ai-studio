"""Fitness Agent API endpoints (LangChain tool calling)."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user_auth, get_db, get_model_service, get_session_service
from app.fitness.schemas import (
    FitnessAgentApproveRequest,
    FitnessAgentApproveResponse,
    FitnessAgentRequest,
    FitnessGoalUpdate,
)
from app.models.database import SessionType
from app.fitness.services.chat_persistence import (
    messages_to_history,
    resolve_fitness_session,
    save_fitness_assistant_message,
    save_fitness_user_message,
)
from app.fitness.services.fitness_service import FitnessService
from app.travel.llm_context import resolve_travel_llm
from app.travel.services.openai_client import get_async_client
from app.fitness.services.fitness_agent_service import fitness_agent_stream
from app.fitness.services.hitl import (
    build_approval_success_message,
    execute_write_tool,
    is_write_tool,
)

router = APIRouter(prefix="/fitness", tags=["fitness"])

DISCLAIMER_DEFAULT = "本工具仅用于生活方式记录与热量估算，非医疗建议。"


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


async def _persist_fitness_stream(
    stream: AsyncIterator[dict[str, Any]],
    session_service,
    session_id: UUID,
) -> AsyncIterator[dict[str, Any]]:
    content_buffer = ""
    tool_trace: list[dict[str, Any]] = []
    pending: dict[str, dict[str, Any]] = {}
    has_error = False
    meal_logged: dict[str, Any] | None = None
    recommendations: list[dict[str, Any]] | None = None

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
                "tool_name": event.get("tool_name") or event.get("tool") or "unknown",
                "tool_args": event.get("tool_args") or event.get("args") or {},
                "status": "pending",
            }
        if etype == "tool_call_result":
            call_id = str(event.get("call_id") or "")
            if not call_id:
                continue
            entry = pending.get(call_id)
            if entry is None:
                continue
            entry["result"] = event.get("result")
            entry["status"] = event.get("status") or ("error" if event.get("error") else "success")
            entry["duration_ms"] = event.get("duration_ms")
            if event.get("error"):
                entry["error"] = event.get("error")
            tool_trace.append(entry)

        if etype == "meal_logged":
            meal_logged = event.get("entry")
        if etype == "recommendations":
            recommendations = event.get("recommendations")

        if etype == "error":
            has_error = True

    if has_error:
        return

    final_content = content_buffer or ""
    if not final_content:
        final_content = "（无回复内容）"

    await save_fitness_assistant_message(
        session_service=session_service,
        session_id=session_id,
        content=final_content,
        tool_trace=tool_trace if tool_trace else None,
        meal_logged=meal_logged,
        recommendations=recommendations,
    )


@router.post("/agent/run")
async def fitness_agent_run(
    request: FitnessAgentRequest,
    user_id: UUID = Depends(get_current_user_auth),
    model_service=Depends(get_model_service),
    session_service=Depends(get_session_service),
    db: AsyncSession = Depends(get_db),
):
    # create a dedicated fitness service from the same DB session
    fitness_service = FitnessService(db)

    try:
        session_id, created = await resolve_fitness_session(
            session_service=session_service,
            user_id=user_id,
            session_id=request.session_id,
            first_message=request.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    stored_messages = await session_service.get_messages(session_id)
    conversation_history = messages_to_history(stored_messages)

    await save_fitness_user_message(
        session_service=session_service,
        session_id=session_id,
        content=request.message,
    )

    # Build OpenAI-compatible client from user's model config (BYOK)
    ctx = await resolve_travel_llm(model_service, user_id, request.model_config_id)
    openai_client = get_async_client(api_key=ctx.api_key, base_url=ctx.base_url)
    model_name = ctx.model_id

    max_rounds = request.max_rounds or 3
    user_timezone = request.timezone

    async def event_stream() -> AsyncIterator[dict[str, Any]]:
        yield {"type": "session", "session_id": str(session_id), "created": created}
        inner = fitness_agent_stream(
            message=request.message,
            conversation_history=conversation_history,
            max_rounds=max_rounds,
            user_timezone=user_timezone,
            user_id=user_id,
            openai_client=openai_client,
            llm_api_key=ctx.api_key,
            llm_base_url=ctx.base_url,
            model_name=model_name,
            fitness_service=fitness_service,
        )
        async for event in _persist_fitness_stream(inner, session_service, session_id):
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


@router.post("/agent/approve", response_model=FitnessAgentApproveResponse)
async def fitness_agent_approve(
    request: FitnessAgentApproveRequest,
    user_id: UUID = Depends(get_current_user_auth),
    session_service=Depends(get_session_service),
    db: AsyncSession = Depends(get_db),
):
    if not is_write_tool(request.tool_name):
        raise HTTPException(status_code=400, detail=f"Tool '{request.tool_name}' does not require approval")

    fitness_service = FitnessService(db)

    try:
        result = await execute_write_tool(
            tool_name=request.tool_name,
            tool_args=request.tool_args,
            fitness_service=fitness_service,
            user_id=user_id,
            user_timezone=request.timezone,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    message = build_approval_success_message(request.tool_name, result)

    if request.session_id:
        session = await session_service.get_session(request.session_id, user_id)
        if session and session.session_type == SessionType.fitness:
            await save_fitness_assistant_message(
                session_service=session_service,
                session_id=request.session_id,
                content=message,
                tool_trace=[
                    {
                        "id": request.call_id or "approved",
                        "tool_name": request.tool_name,
                        "tool_args": request.tool_args,
                        "status": "success",
                        "result": result,
                    }
                ],
                meal_logged=result if request.tool_name == "log_meal" else None,
            )

    return FitnessAgentApproveResponse(
        ok=True,
        tool_name=request.tool_name,
        result=result,
        message=message,
    )


@router.get("/goals")
async def fitness_get_goals(
    user_id: UUID = Depends(get_current_user_auth),
    session_service=Depends(get_session_service),
    db: AsyncSession = Depends(get_db),
):
    fitness_service = FitnessService(db)
    return (await fitness_service.get_goal(user_id)).model_dump()


@router.put("/goals")
async def fitness_put_goals(
    update: FitnessGoalUpdate,
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    fitness_service = FitnessService(db)
    return (await fitness_service.set_goal(user_id, update.daily_calorie_goal)).model_dump()


@router.get("/diary/today")
async def fitness_today_diary(
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
    timezone: str | None = None,
):
    fitness_service = FitnessService(db)
    return (
        await fitness_service.get_today_summary(
            user_id,
            timezone_name=timezone,
        )
    ).model_dump()


@router.delete("/diary/{entry_id}")
async def fitness_delete_diary_entry(
    entry_id: str,
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    fitness_service = FitnessService(db)
    ok = await fitness_service.delete_entry(user_id, entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"ok": True}

