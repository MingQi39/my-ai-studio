"""Spider Agent API endpoints."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Literal
from uuid import UUID

import mimetypes

import aiohttp

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
    save_spider_user_message,
    upsert_spider_assistant_message,
)
from app.spider.services.html_preview import (
    collect_preview_image_urls,
    is_safe_remote_url,
    prepare_html_for_preview,
)
from app.spider.services.sandbox import initialize_session_sandbox, list_workspace_files
from app.spider.services.spider_agent_service import spider_agent_stream
from app.spider.services.stream_checkpoint import (
    SpiderCheckpointState,
    apply_persist_event,
    has_persistable_snapshot,
    ordered_tool_trace,
    resolve_persist_content,
)
from app.travel.llm_context import resolve_travel_llm

router = APIRouter(prefix="/spider", tags=["spider"])

CHUNK_CHECKPOINT_INTERVAL_S = 2.0
CHUNK_CHECKPOINT_MIN_CHARS = 200


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
    state = SpiderCheckpointState()
    assistant_message_id: UUID | None = None
    last_flush_at = 0.0
    chars_since_flush = 0
    finalized = False

    async def flush(*, is_complete: bool) -> None:
        nonlocal assistant_message_id, last_flush_at, chars_since_flush, finalized
        if not has_persistable_snapshot(state):
            return
        if is_complete:
            finalized = True
        content = resolve_persist_content(state, complete=is_complete)
        trace = ordered_tool_trace(state)
        try:
            assistant_message_id = await upsert_spider_assistant_message(
                session_service=session_service,
                session_id=session_id,
                message_id=assistant_message_id,
                content=content,
                tool_trace=trace if trace else None,
                failure=state.failure,
                todos=state.latest_todos,
                is_complete=is_complete,
            )
        except Exception:
            # checkpoint failure must not kill SSE
            pass
        last_flush_at = asyncio.get_running_loop().time()
        chars_since_flush = 0

    try:
        async for event in stream:
            yield event
            action = apply_persist_event(state, event)

            if action == "immediate":
                await flush(is_complete=False)
            elif action == "debounced":
                chars_since_flush += len(str(event.get("content") or ""))
                now = asyncio.get_running_loop().time()
                if (
                    chars_since_flush >= CHUNK_CHECKPOINT_MIN_CHARS
                    or (now - last_flush_at) >= CHUNK_CHECKPOINT_INTERVAL_S
                ):
                    await flush(is_complete=False)

        if has_persistable_snapshot(state):
            await flush(is_complete=True)
    except asyncio.CancelledError:
        if not finalized and has_persistable_snapshot(state):
            await flush(is_complete=False)
            finalized = True
        raise
    finally:
        if not finalized and has_persistable_snapshot(state):
            await flush(is_complete=False)


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


def _read_source_page_url(workspace) -> str | None:
    raw = workspace.read_text("source_page.meta.json")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    url = data.get("url") if isinstance(data, dict) else None
    return url.strip() if isinstance(url, str) and url.strip() else None


async def _fetch_preview_asset(url: str, referer: str | None) -> tuple[bytes, str]:
    if not is_safe_remote_url(url):
        raise ValueError("unsafe url")
    if referer and not is_safe_remote_url(referer):
        referer = None

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    if referer:
        headers["Referer"] = referer

    timeout = aiohttp.ClientTimeout(total=12)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers) as response:
            if response.status >= 400:
                raise RuntimeError(f"asset fetch failed: {response.status}")
            data = await response.read()
            content_type = response.headers.get("Content-Type") or "application/octet-stream"
            return data, content_type


@router.get("/workspace/{session_id}/files/{filename}/html-preview")
async def spider_workspace_html_preview(
    session_id: UUID,
    filename: str,
    user_id: UUID = Depends(get_current_user_auth),
    session_service=Depends(get_session_service),
):
    """Return HTML with remote images inlined so blob: previews bypass hotlink blocks."""
    safe_name = _validate_workspace_filename(filename)
    if not safe_name.lower().endswith((".html", ".htm")):
        raise HTTPException(status_code=400, detail="Not an HTML file")

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

    html = workspace.read_text(safe_name)
    if html is None:
        raise HTTPException(status_code=404, detail="File not found")

    meta_url = _read_source_page_url(workspace)
    resolved_base, image_urls = collect_preview_image_urls(html, meta_url)

    async def _safe_fetch(url: str) -> tuple[str, tuple[bytes, str] | None]:
        try:
            return url, await _fetch_preview_asset(url, resolved_base)
        except Exception:
            return url, None

    fetched = await asyncio.gather(*[_safe_fetch(url) for url in image_urls])
    assets = {url: payload for url, payload in fetched if payload is not None}

    def sync_fetch(url: str, referer: str | None) -> tuple[bytes, str]:
        del referer
        payload = assets.get(url)
        if payload is None:
            raise RuntimeError("asset unavailable")
        return payload

    rewritten = prepare_html_for_preview(html, base_url=meta_url, fetch_asset=sync_fetch)
    return Response(content=rewritten.encode("utf-8"), media_type="text/html; charset=utf-8")
