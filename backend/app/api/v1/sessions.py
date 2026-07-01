"""
会话管理端点

提供会话的 CRUD 操作、配置管理和消息查询
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_current_user_auth, get_session_service
from app.models.schemas import (
    PaginatedResponse,
    SessionConfigResponse,
    SessionConfigUpdate,
    SessionCreate,
    SessionDetailResponse,
    SessionResponse,
    SessionUpdate,
    MessageResponse,
)
from app.services.session_service import SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse)
async def create_session(
    data: SessionCreate,
    user_id: UUID = Depends(get_current_user_auth),
    session_service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """创建新会话"""
    session = await session_service.create_session(user_id, data)
    return SessionResponse.from_orm(session)


@router.get("", response_model=PaginatedResponse[SessionResponse])
async def list_sessions(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    include_archived: bool = Query(False, description="是否包含已归档会话"),
    session_type: str | None = Query(
        "chat",
        description="会话类型过滤：chat / travel；传 all 表示不过滤",
    ),
    user_id: UUID = Depends(get_current_user_auth),
    session_service: SessionService = Depends(get_session_service),
) -> PaginatedResponse[SessionResponse]:
    """列出用户会话"""
    from app.models.database import SessionType
    from app.models.schemas import PaginationParams

    params = PaginationParams(page=page, page_size=page_size)
    type_filter: SessionType | None
    if session_type is None or session_type == "all":
        type_filter = None
    else:
        try:
            type_filter = SessionType(session_type)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid session_type") from exc

    result = await session_service.list_sessions(
        user_id, params, include_archived, session_type=type_filter
    )
    return result


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: UUID,
    user_id: UUID = Depends(get_current_user_auth),
    session_service: SessionService = Depends(get_session_service),
) -> SessionDetailResponse:
    """获取会话详情（含消息）"""
    session = await session_service.get_session(session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != str(user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    return SessionDetailResponse.from_orm(session)


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: UUID,
    data: SessionUpdate,
    user_id: UUID = Depends(get_current_user_auth),
    session_service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """更新会话信息"""
    session = await session_service.update_session(session_id, user_id, data)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse.from_orm(session)


@router.delete("/{session_id}")
async def delete_session(
    session_id: UUID,
    user_id: UUID = Depends(get_current_user_auth),
    session_service: SessionService = Depends(get_session_service),
) -> dict:
    """删除会话"""
    success = await session_service.delete_session(session_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"success": True}


@router.get("/{session_id}/config", response_model=SessionConfigResponse)
async def get_session_config(
    session_id: UUID,
    user_id: UUID = Depends(get_current_user_auth),
    session_service: SessionService = Depends(get_session_service),
) -> SessionConfigResponse:
    """获取会话配置"""
    # 先验证会话归属
    session = await session_service.get_session(session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != str(user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    config = await session_service.get_session_config(session_id)
    if not config:
        raise HTTPException(status_code=404, detail="Session config not found")

    return SessionConfigResponse.from_orm(config)


@router.patch("/{session_id}/config", response_model=SessionConfigResponse)
async def update_session_config(
    session_id: UUID,
    data: SessionConfigUpdate,
    user_id: UUID = Depends(get_current_user_auth),
    session_service: SessionService = Depends(get_session_service),
) -> SessionConfigResponse:
    """更新会话配置"""
    config = await session_service.update_session_config(session_id, user_id, data)
    if not config:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionConfigResponse.from_orm(config)


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
async def get_session_messages(
    session_id: UUID,
    limit: int = Query(50, ge=1, le=100, description="消息数量限制"),
    before_id: UUID | None = Query(None, description="游标分页：获取此 ID 之前的消息"),
    user_id: UUID = Depends(get_current_user_auth),
    session_service: SessionService = Depends(get_session_service),
) -> list[MessageResponse]:
    """获取会话消息历史"""
    # 先验证会话归属
    session = await session_service.get_session(session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != str(user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    messages = await session_service.get_messages(session_id, limit, before_id)
    
    import logging
    logger = logging.getLogger(__name__)
    
    # 手动构建MessageResponse，包含附件信息
    result = []
    for msg in messages:
        # 加载附件信息
        attachments_data = []
        if hasattr(msg, 'attachments') and msg.attachments:
            logger.info(f"Message {msg.id} has {len(msg.attachments)} attachments")
            for attachment in msg.attachments:
                if hasattr(attachment, 'file') and attachment.file:
                    file = attachment.file
                    logger.info(f"  Attachment file: {file.id}, name={file.name}, url={file.url}")
                    attachments_data.append({
                        'id': file.id,
                        'name': file.name,
                        'type': file.type,
                        'mime_type': file.mime_type,
                        'size': file.size,
                        'url': file.url,
                        'created_at': file.created_at,
                    })
                else:
                    logger.warning(f"  Attachment has no file object")
        else:
            logger.info(f"Message {msg.id} has no attachments")
        
        result.append(MessageResponse(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            thinking_content=msg.thinking_content,
            tokens_used=msg.tokens_used,
            model_used=msg.model_used,
            provider_used=msg.provider_used,
            tool_calls=msg.tool_calls,
            created_at=msg.created_at,
            attachments=attachments_data if attachments_data else None
        ))
    
    logger.info(f"Returning {len(result)} messages with attachments info")
    return result

