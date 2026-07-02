"""
聊天端点

提供流式和非流式聊天接口
"""
import asyncio
import json
from typing import Any, AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.adapters.types import ChatCompletionChunk
from app.core.exceptions import LLMException
from app.core.stream_state import stream_state_manager
from app.dependencies import get_current_user_auth, get_chat_service, get_session_service
from app.models.database import MessageRole
from app.models.schemas import ChatRequest, MessageResponse
from app.services.chat_service import ChatService
from app.services.session_service import SessionService
from app.utils.logging import get_logger

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)


async def _stream_chat_events(
    chat_service: ChatService,
    session_id: UUID,
    user_id: UUID,
    request: ChatRequest,
    *,
    retry: bool = False,
) -> AsyncIterator[str]:
    """将 chat/retry 生成器转为 SSE；客户端断开后生成任务继续在后台运行。"""
    queue: asyncio.Queue[tuple[str, ChatCompletionChunk | dict[str, Any] | None]] = asyncio.Queue(maxsize=512)

    async def produce() -> None:
        try:
            stream = (
                chat_service.retry_incomplete(session_id, user_id, request)
                if retry
                else chat_service.chat(session_id, user_id, request)
            )
            async for chunk in stream:
                await queue.put(("chunk", chunk))
            await queue.put(("done", None))
        except LLMException as e:
            error_data = {
                "type": "error",
                "error": e.error_code,
                "message": e.message,
                "details": e.details,
            }
            await queue.put(("error", error_data))
            logger.error(f"Chat error: {e.error_code}", exc_info=True)
        except Exception as e:
            from app.core.exceptions import ConfigurationError

            if isinstance(e, ConfigurationError):
                error_data = {
                    "type": "error",
                    "error": "CONFIGURATION_ERROR",
                    "message": e.reason,
                    "config_key": e.config_key,
                }
                logger.warning(f"Configuration error: {e.reason}")
            else:
                error_data = {
                    "type": "error",
                    "error": "INTERNAL_ERROR",
                    "message": f"An unexpected error occurred: {str(e)}",
                }
                logger.error(f"Unexpected chat error: {str(e)}", exc_info=True)
            await queue.put(("error", error_data))

    producer = asyncio.create_task(produce())

    try:
        while True:
            kind, payload = await queue.get()
            if kind == "done":
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break
            if kind == "error":
                yield f"data: {json.dumps(payload)}\n\n"
                break
            yield f"data: {json.dumps(payload)}\n\n"
    except asyncio.CancelledError:
        logger.info(
            "Client disconnected from stream for session %s; generation continues in background",
            session_id,
        )
        raise
    finally:
        if not producer.done():
            producer.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)


async def generate_sse(
    chat_service: ChatService,
    session_id: UUID,
    user_id: UUID,
    request: ChatRequest,
) -> AsyncIterator[str]:
    """SSE 生成器"""
    async for event in _stream_chat_events(chat_service, session_id, user_id, request):
        yield event


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    user_id: UUID = Depends(get_current_user_auth),
    chat_service: ChatService = Depends(get_chat_service),
    session_service: SessionService = Depends(get_session_service),
) -> StreamingResponse:
    """流式聊天（SSE）"""
    # 验证会话归属
    session = await session_service.get_session(request.session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != str(user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    # 返回 SSE 流式响应
    return StreamingResponse(
        generate_sse(chat_service, request.session_id, user_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )


@router.post("/complete", response_model=MessageResponse)
async def complete_chat(
    request: ChatRequest,
    user_id: UUID = Depends(get_current_user_auth),
    chat_service: ChatService = Depends(get_chat_service),
    session_service: SessionService = Depends(get_session_service),
) -> MessageResponse:
    """非流式聊天"""
    # 验证会话归属
    session = await session_service.get_session(request.session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != str(user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    # 调用非流式聊天
    message = await chat_service.chat_complete(request.session_id, user_id, request)
    return MessageResponse.from_orm(message)


@router.get("/stream-status/{session_id}")
async def get_stream_status(
    session_id: UUID,
    user_id: UUID = Depends(get_current_user_auth),
    session_service: SessionService = Depends(get_session_service),
):
    """检查指定会话是否有活跃的流式生成"""
    session = await session_service.get_session(session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != str(user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    state = stream_state_manager.get(str(session_id))
    if state and state.message_id:
        message = await session_service.get_message(UUID(state.message_id))
        if message is None or message.is_complete:
            stream_state_manager.unregister(str(session_id))
            state = None

    is_active = state is not None and state.is_active
    is_complete = None
    if state and state.message_id:
        message = await session_service.get_message(UUID(state.message_id))
        is_complete = message.is_complete if message else None
    elif not is_active:
        messages = await session_service.get_messages(session_id, limit=1)
        if messages and messages[0].role == MessageRole.assistant:
            is_complete = messages[0].is_complete

    return {
        "session_id": str(session_id),
        "is_streaming": is_active,
        "message_id": state.message_id if state else None,
        "content": state.content if state and state.content else None,
        "thinking": state.thinking if state and state.thinking else None,
        "is_complete": is_complete,
    }


@router.get("/stream-resume/{session_id}")
async def resume_stream(
    session_id: UUID,
    user_id: UUID = Depends(get_current_user_auth),
    session_service: SessionService = Depends(get_session_service),
):
    """恢复流式连接：先发送已生成内容，然后转发后续 chunk"""
    session = await session_service.get_session(session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != str(user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    state = stream_state_manager.get(str(session_id))
    if not state or not state.is_active:
        raise HTTPException(status_code=404, detail="No active stream for this session")

    async def resume_generator() -> AsyncIterator[str]:
        # 1. 发送已生成的内容和思考
        if state.content:
            yield f"data: {json.dumps({'type': 'content', 'content': state.content})}\n\n"
        if state.thinking:
            yield f"data: {json.dumps({'type': 'thinking', 'thinking': state.thinking})}\n\n"
        
        # 2. 发送 tool_results（如果有）
        for tr in state.tool_results:
            yield f"data: {json.dumps({'type': 'tool_result', 'tool_result': tr})}\n\n"
        
        # 3. 持续轮询，转发后续增量内容
        last_content_len = len(state.content)
        last_thinking_len = len(state.thinking)
        last_tool_results_len = len(state.tool_results)
        import asyncio

        idle_rounds = 0
        max_idle_rounds = 150  # ~30s without progress

        while state.is_active:
            await asyncio.sleep(0.2)

            message = await session_service.get_message(UUID(state.message_id))
            if message and message.is_complete:
                state.is_active = False
                break

            # 检查是否有新内容
            new_content = state.content[last_content_len:]
            new_thinking = state.thinking[last_thinking_len:]

            if new_content:
                yield f"data: {json.dumps({'type': 'content', 'content': new_content})}\n\n"
                last_content_len = len(state.content)
                idle_rounds = 0
            elif new_thinking:
                yield f"data: {json.dumps({'type': 'thinking', 'thinking': new_thinking})}\n\n"
                last_thinking_len = len(state.thinking)
                idle_rounds = 0
            elif len(state.tool_results) > last_tool_results_len:
                for tr in state.tool_results[last_tool_results_len:]:
                    yield f"data: {json.dumps({'type': 'tool_result', 'tool_result': tr})}\n\n"
                last_tool_results_len = len(state.tool_results)
                idle_rounds = 0
            else:
                idle_rounds += 1
                if idle_rounds >= max_idle_rounds:
                    stream_state_manager.unregister(str(session_id))
                    break
        
        # 流结束
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        resume_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/retry/{session_id}")
async def retry_chat_stream(
    session_id: UUID,
    request: ChatRequest,
    user_id: UUID = Depends(get_current_user_auth),
    chat_service: ChatService = Depends(get_chat_service),
    session_service: SessionService = Depends(get_session_service),
) -> StreamingResponse:
    """重试未完成的 assistant 回复（删除残缺消息后重新生成）"""
    session = await session_service.get_session(session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != str(user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    return StreamingResponse(
        _stream_chat_events(chat_service, session_id, user_id, request, retry=True),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history/{session_id}", response_model=list[MessageResponse])
async def get_chat_history(
    session_id: UUID,
    limit: int = Query(50, ge=1, le=100, description="消息数量限制"),
    user_id: UUID = Depends(get_current_user_auth),
    session_service: SessionService = Depends(get_session_service),
) -> list[MessageResponse]:
    """获取聊天历史"""
    # 验证会话归属
    session = await session_service.get_session(session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != str(user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    # 获取消息历史
    messages = await session_service.get_messages(session_id, limit)
    return [MessageResponse.from_orm(msg) for msg in messages]
