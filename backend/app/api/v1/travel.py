"""Travel Agent API endpoints (ReAct, tools, compare)."""

import asyncio
import json
import time
from typing import Any, AsyncIterator, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from app.dependencies import get_current_user_auth, get_model_service, get_session_service
from app.services.model_service import ModelService
from app.services.session_service import SessionService
from app.travel.config.defaults import Settings
from app.travel.config.user_settings import get_user_travel_settings, save_user_travel_settings
from app.travel.itinerary_models import (
    TravelPlanGenerateRequest,
    TravelPlanGenerateResponse,
    TravelPlanStatusResponse,
)
from app.travel.llm_context import resolve_travel_llm
from app.travel.models import ToolTestRequest
from app.travel.services.chat_persistence import (
    collect_agent_thinking_event,
    messages_to_history,
    resolve_travel_session,
    save_travel_assistant_message,
    save_travel_user_message,
)
from app.travel.services.formal_plan_storage import (
    clear_formal_plan,
    compute_plan_fingerprint,
    get_formal_plan_status,
    save_formal_plan,
)
from app.travel.services.itinerary_service import generate_structured_plan, resolve_plan_inputs
from app.travel.services.llm_service import LLMService
from app.travel.services.openai_client import get_async_client
from app.travel.services.react_agent import ReActAgent
from app.travel.services.sse_merge import merge_streams
from app.travel.services.tool_registry import ToolsRegistry
from app.travel.tools.builtin import register_builtin_tools

router = APIRouter(prefix="/travel", tags=["travel"])

SECRET_FIELDS = ("amap_api_key", "tavily_api_key", "juhe_train_api_key", "juhe_flight_api_key")
TRAVEL_SYSTEM_PROMPT = "你是一个旅行规划助手。请根据用户需求提供建议。"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class TravelChatRequest(BaseModel):
    message: str
    mode: Literal["llm", "agent"] = "agent"
    history: list[ChatMessage] = Field(default_factory=list)
    session_id: UUID | None = None
    max_rounds: int | None = None
    model_config_id: UUID


class TravelCompareRequest(BaseModel):
    message: str
    session_id: UUID | None = None
    max_rounds: int | None = None
    model_config_id: UUID


class TravelAgentRequest(BaseModel):
    message: str
    max_rounds: int | None = None
    model_config_id: UUID


class TravelSettingsUpdate(BaseModel):
    max_rounds: int | None = None


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


def _create_registry() -> ToolsRegistry:
    registry = ToolsRegistry()
    register_builtin_tools(registry)
    return registry


async def _build_llm(
    model_service: ModelService,
    user_id: UUID,
    model_config_id: UUID,
) -> tuple[Any, str]:
    ctx = await resolve_travel_llm(model_service, user_id, model_config_id)
    client = get_async_client(api_key=ctx.api_key, base_url=ctx.base_url)
    return client, ctx.model_id


async def format_sse_stream(stream: AsyncIterator[dict]) -> AsyncIterator[str]:
    async for event in stream:
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0)


async def safe_agent_stream(
    agent: ReActAgent,
    message: str,
    max_rounds: int,
    conversation_history: list[dict[str, str]] | None = None,
) -> AsyncIterator[dict]:
    try:
        async for event in agent.run(
            message,
            max_rounds=max_rounds,
            conversation_history=conversation_history,
        ):
            yield event
    except Exception as exc:
        yield {
            "type": "error",
            "source": "agent",
            "error_type": "agent_runtime_error",
            "message": f"Agent 运行失败: {exc}",
            "recoverable": False,
        }
        yield {
            "type": "done",
            "source": "agent",
            "stats": {"llm_calls": 0, "tool_calls": 0, "duration_ms": 0},
        }


async def _persist_chat_stream(
    stream: AsyncIterator[dict],
    session_service: SessionService,
    session_id: UUID,
    mode: str,
) -> AsyncIterator[dict]:
    content_buffer = ""
    thinking_steps: list[dict[str, Any]] = []
    pending_tool_calls: dict[str, dict[str, Any]] = {}
    has_error = False

    async for event in stream:
        yield event
        if event.get("type") == "chunk" and event.get("content"):
            content_buffer += event["content"]
        if event.get("type") == "final_response" and event.get("content"):
            content_buffer = event["content"]
        if mode == "agent":
            collect_agent_thinking_event(event, thinking_steps, pending_tool_calls)
        if event.get("type") == "error":
            has_error = True

    if has_error:
        return

    final_content = content_buffer
    if mode == "agent" and not final_content and thinking_steps:
        think_steps = [s for s in thinking_steps if s.get("type") == "Think"]
        if think_steps:
            final_content = think_steps[-1]["content"]

    if not final_content:
        final_content = "（无回复内容）"

    await save_travel_assistant_message(
        session_service,
        session_id,
        final_content,
        mode=mode,
        thinking_steps=thinking_steps if mode == "agent" else None,
    )


async def _persist_compare_stream(
    llm_stream: AsyncIterator[dict],
    agent_stream: AsyncIterator[dict],
    session_service: SessionService,
    session_id: UUID,
) -> AsyncIterator[str]:
    compare_group = str(int(time.time() * 1000))
    llm_content = ""
    agent_content = ""
    agent_steps: list[dict[str, Any]] = []
    pending_tool_calls: dict[str, dict[str, Any]] = {}
    llm_done = False
    agent_done = False
    llm_error = False
    agent_error = False

    async for sse_line in merge_streams(llm_stream, agent_stream):
        yield sse_line
        if not sse_line.startswith("data: "):
            continue
        try:
            event = json.loads(sse_line[6:].strip())
        except json.JSONDecodeError:
            continue

        source = event.get("source")
        if source == "llm":
            if event.get("type") == "chunk" and event.get("content"):
                llm_content += event["content"]
            if event.get("type") == "done":
                llm_done = True
            if event.get("type") == "error":
                llm_error = True
        elif source == "agent":
            if event.get("type") == "final_response" and event.get("content"):
                agent_content = event["content"]
            if event.get("type") == "chunk" and event.get("content"):
                agent_content += event["content"]
            collect_agent_thinking_event(event, agent_steps, pending_tool_calls)
            if event.get("type") == "done":
                agent_done = True
            if event.get("type") == "error":
                agent_error = True

    if llm_done and not llm_error and llm_content:
        await save_travel_assistant_message(
            session_service,
            session_id,
            llm_content,
            mode="compare_llm",
            compare_group=compare_group,
        )
    if agent_done and not agent_error:
        if not agent_content and agent_steps:
            think_steps = [s for s in agent_steps if s.get("type") == "Think"]
            if think_steps:
                agent_content = think_steps[-1]["content"]
        if agent_content:
            await save_travel_assistant_message(
                session_service,
                session_id,
                agent_content,
                mode="compare_agent",
                thinking_steps=agent_steps,
                compare_group=compare_group,
            )


@router.post("/chat")
async def travel_chat(
    request: TravelChatRequest,
    user_id: UUID = Depends(get_current_user_auth),
    model_service: ModelService = Depends(get_model_service),
    session_service: SessionService = Depends(get_session_service),
):
    try:
        session_id, created = await resolve_travel_session(
            session_service,
            user_id,
            request.session_id,
            request.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    stored_messages = await session_service.get_messages(session_id)
    conversation_history = messages_to_history(stored_messages)
    await save_travel_user_message(session_service, session_id, request.message, user_id=user_id)

    openai_client, model_name = await _build_llm(model_service, user_id, request.model_config_id)
    user_settings = get_user_travel_settings(user_id)
    max_rounds = request.max_rounds or user_settings.max_rounds

    async def event_stream() -> AsyncIterator[dict]:
        yield {"type": "session", "session_id": str(session_id), "created": created}

        if request.mode == "llm":
            llm_service = LLMService(openai_client=openai_client, model_name=model_name)
            messages = [{"role": "system", "content": TRAVEL_SYSTEM_PROMPT}]
            for msg in conversation_history:
                messages.append(msg)
            messages.append({"role": "user", "content": request.message})
            inner = llm_service.stream_with_history(messages)
        else:
            react_agent = ReActAgent(
                tools_registry=_create_registry(),
                openai_client=openai_client,
                model_name=model_name,
            )
            inner = safe_agent_stream(
                react_agent,
                request.message,
                max_rounds,
                conversation_history=conversation_history,
            )

        async for event in _persist_chat_stream(
            inner,
            session_service,
            session_id,
            request.mode,
        ):
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


@router.post("/compare")
async def travel_compare(
    request: TravelCompareRequest,
    user_id: UUID = Depends(get_current_user_auth),
    model_service: ModelService = Depends(get_model_service),
    session_service: SessionService = Depends(get_session_service),
):
    try:
        session_id, created = await resolve_travel_session(
            session_service,
            user_id,
            request.session_id,
            request.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    stored_messages = await session_service.get_messages(session_id)
    conversation_history = messages_to_history(stored_messages)
    await save_travel_user_message(session_service, session_id, request.message, user_id=user_id)

    openai_client, model_name = await _build_llm(model_service, user_id, request.model_config_id)
    user_settings = get_user_travel_settings(user_id)
    max_rounds = request.max_rounds or user_settings.max_rounds

    llm_service = LLMService(openai_client=openai_client, model_name=model_name)
    react_agent = ReActAgent(
        tools_registry=_create_registry(),
        openai_client=openai_client,
        model_name=model_name,
    )

    llm_messages = [{"role": "system", "content": TRAVEL_SYSTEM_PROMPT}]
    for msg in conversation_history:
        llm_messages.append(msg)
    llm_messages.append({"role": "user", "content": request.message})

    llm_stream = llm_service.stream_with_history(llm_messages)
    agent_stream = safe_agent_stream(
        react_agent,
        request.message,
        max_rounds=max_rounds,
        conversation_history=conversation_history,
    )

    async def compare_sse() -> AsyncIterator[str]:
        yield f"data: {json.dumps({'type': 'session', 'session_id': str(session_id), 'created': created}, ensure_ascii=False)}\n\n"
        async for line in _persist_compare_stream(
            llm_stream,
            agent_stream,
            session_service,
            session_id,
        ):
            yield line

    return StreamingResponse(
        compare_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/agent/run")
async def travel_agent_run(
    request: TravelAgentRequest,
    user_id: UUID = Depends(get_current_user_auth),
    model_service: ModelService = Depends(get_model_service),
):
    openai_client, model_name = await _build_llm(model_service, user_id, request.model_config_id)
    user_settings = get_user_travel_settings(user_id)
    max_rounds = request.max_rounds or user_settings.max_rounds

    react_agent = ReActAgent(
        tools_registry=_create_registry(),
        openai_client=openai_client,
        model_name=model_name,
    )

    async def event_stream() -> AsyncIterator[str]:
        async for event in react_agent.run(request.message, max_rounds=max_rounds):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/tools/list")
async def travel_list_tools(
    _user_id: UUID = Depends(get_current_user_auth),
) -> list[dict[str, Any]]:
    return _create_registry().list_tools()


@router.get("/tools/{tool_name}")
async def travel_get_tool(
    tool_name: str,
    _user_id: UUID = Depends(get_current_user_auth),
) -> dict[str, Any]:
    for tool in _create_registry().list_tools():
        if tool["name"] == tool_name:
            return tool
    raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")


@router.post("/tools/{tool_name}/test", response_model=None)
async def travel_test_tool(
    tool_name: str,
    request: ToolTestRequest,
    _user_id: UUID = Depends(get_current_user_auth),
) -> dict[str, Any] | JSONResponse:
    registry = _create_registry()
    if tool_name not in registry.tool_names:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    start = time.time()
    result = await registry.execute(tool_name, request.args)
    duration_ms = int((time.time() - start) * 1000)

    parsed_result: Any = result
    error: str | None = None
    try:
        parsed = json.loads(result)
        parsed_result = parsed
        if isinstance(parsed, dict) and parsed.get("error"):
            error = str(parsed["error"])
    except (json.JSONDecodeError, TypeError):
        parsed_result = result

    response = {
        "ok": error is None,
        "tool_name": tool_name,
        "result": parsed_result,
        "error": error,
        "duration_ms": duration_ms,
    }
    if error is not None:
        return JSONResponse(status_code=400, content=response)
    return response


@router.get("/settings")
async def travel_get_settings(
    user_id: UUID = Depends(get_current_user_auth),
) -> dict[str, Any]:
    env_settings = Settings()
    user_settings = get_user_travel_settings(user_id)
    payload = {
        "max_rounds": user_settings.max_rounds,
        "amap_api_key": _mask_secret(env_settings.amap_api_key),
        "tavily_api_key": _mask_secret(env_settings.tavily_api_key),
        "juhe_train_api_key": _mask_secret(env_settings.juhe_train_api_key),
        "juhe_flight_api_key": _mask_secret(env_settings.juhe_flight_api_key),
        "tools_configured": bool(
            env_settings.amap_api_key
            and (env_settings.juhe_train_api_key or env_settings.juhe_flight_api_key)
        ),
    }
    return payload


@router.post("/settings")
async def travel_update_settings(
    update: TravelSettingsUpdate,
    user_id: UUID = Depends(get_current_user_auth),
) -> dict[str, str]:
    if update.max_rounds is not None:
        if update.max_rounds < 1 or update.max_rounds > 10:
            raise HTTPException(status_code=400, detail="max_rounds 必须在 1-10 之间")
        save_user_travel_settings(user_id, update.max_rounds)
    return {"message": "Travel settings updated successfully"}


@router.post("/plan/generate", response_model=TravelPlanGenerateResponse)
async def travel_generate_plan(
    request: TravelPlanGenerateRequest,
    user_id: UUID = Depends(get_current_user_auth),
    model_service: ModelService = Depends(get_model_service),
    session_service: SessionService = Depends(get_session_service),
) -> TravelPlanGenerateResponse:
    try:
        user_request, assistant_plan, data_verified = await resolve_plan_inputs(
            session_service,
            user_id,
            session_id=request.session_id,
            user_request=request.user_request,
            assistant_plan=request.assistant_plan,
            data_verified=request.data_verified,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        openai_client, model_name = await _build_llm(
            model_service,
            user_id,
            request.model_config_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        response = await generate_structured_plan(
            openai_client,
            model_name,
            user_request=user_request,
            assistant_plan=assistant_plan,
            tool_evidence=request.tool_evidence,
            data_verified=data_verified,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"生成结构化行程失败: {exc}") from exc

    fingerprint = compute_plan_fingerprint(user_request, assistant_plan)
    generated_at = None

    if request.session_id:
        try:
            await save_formal_plan(
                session_service,
                request.session_id,
                user_id,
                fingerprint=fingerprint,
                response=response,
            )
            status = await get_formal_plan_status(session_service, request.session_id, user_id)
            generated_at = status.generated_at
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return TravelPlanGenerateResponse(
        plan=response.plan,
        markdown=response.markdown,
        fingerprint=fingerprint,
        exists=True,
        is_stale=False,
        generated_at=generated_at,
    )


@router.get("/plan/session/{session_id}", response_model=TravelPlanStatusResponse)
async def travel_get_formal_plan(
    session_id: UUID,
    user_id: UUID = Depends(get_current_user_auth),
    session_service: SessionService = Depends(get_session_service),
) -> TravelPlanStatusResponse:
    try:
        return await get_formal_plan_status(session_service, session_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/plan/session/{session_id}/pdf")
async def travel_download_formal_plan_pdf(
    session_id: UUID,
    user_id: UUID = Depends(get_current_user_auth),
    session_service: SessionService = Depends(get_session_service),
) -> Response:
    try:
        status = await get_formal_plan_status(session_service, session_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not status.exists or not status.plan or not status.markdown:
        raise HTTPException(status_code=404, detail="正式规划书不存在")
    if status.is_stale:
        raise HTTPException(status_code=409, detail="对话已更新，请重新生成正式规划书后再导出")

    try:
        from app.travel.services.plan_pdf_service import (
            render_markdown_pdf,
            sanitize_pdf_filename,
        )

        pdf_bytes = render_markdown_pdf(status.markdown, status.plan.title)
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="PDF 导出依赖未安装，请在后端执行 pip install markdown fpdf2",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    filename = f"{sanitize_pdf_filename(status.plan.title)}.pdf"
    encoded = quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename=\"{encoded}\"; filename*=UTF-8''{encoded}",
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
