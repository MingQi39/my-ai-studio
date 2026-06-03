"""
聊天端点

提供流式和非流式聊天接口
"""
import json
from typing import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.exceptions import LLMException
from app.dependencies import get_current_user_auth, get_chat_service, get_session_service
from app.models.schemas import ChatRequest, MessageResponse
from app.services.chat_service import ChatService
from app.services.session_service import SessionService
from app.utils.logging import get_logger

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)


async def generate_sse(
    chat_service: ChatService,
    session_id: UUID,
    user_id: UUID,
    request: ChatRequest,
) -> AsyncIterator[str]:
    """SSE 生成器"""
    try:
        async for chunk in chat_service.chat(session_id, user_id, request):
            # 将 chunk 转换为 JSON 字符串
            chunk_data = chunk.dict() if hasattr(chunk, "dict") else chunk
            yield f"data: {json.dumps(chunk_data)}\n\n"

        # 发送完成信号
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except LLMException as e:
        # 发送错误信息
        error_data = {
            "type": "error",
            "error": e.error_code,
            "message": e.message,
            "details": e.details,
        }
        yield f"data: {json.dumps(error_data)}\n\n"
        logger.error(f"Chat error: {e.error_code}", exc_info=True)
        
    except Exception as e:
        # 检查是否是 ConfigurationError
        from app.core.exceptions import ConfigurationError
        if isinstance(e, ConfigurationError):
            error_data = {
                "type": "error",
                "error": "CONFIGURATION_ERROR",
                "message": e.reason,
                "config_key": e.config_key,
            }
            yield f"data: {json.dumps(error_data)}\n\n"
            logger.warning(f"Configuration error: {e.reason}")
        else:
            # 发送通用错误
            import traceback
            error_msg = f"Unexpected chat error: {str(e)}\n{traceback.format_exc()}"
            print(f"CRITICAL ERROR IN GENERATE_SSE:\n{error_msg}", flush=True)  # 强制打印到控制台
            
            error_data = {
                "type": "error",
                "error": "INTERNAL_ERROR",
                "message": f"An unexpected error occurred: {str(e)}",  # 临时将错误详情暴露给前端以便调试
            }
            yield f"data: {json.dumps(error_data)}\n\n"
            logger.error(f"Unexpected chat error: {str(e)}", exc_info=True)


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
