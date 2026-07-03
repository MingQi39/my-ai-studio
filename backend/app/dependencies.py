"""
依赖注入

提供 FastAPI 的依赖注入函数，用于共享资源和服务实例
"""
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.database import get_db as db_get_db

if TYPE_CHECKING:
    from app.services.batch_service import BatchService
    from app.services.chat_service import ChatService
    from app.services.file_service import FileService
    from app.services.model_service import ModelService
    from app.services.session_service import SessionService
    from app.services.user_service import UserService


# HTTP Bearer 认证
security = HTTPBearer(auto_error=False)


def get_settings_dependency() -> Settings:
    """获取应用配置

    Returns:
        Settings: 应用配置实例
    """
    return get_settings()


def get_logger_dependency(name: str = "app") -> structlog.stdlib.BoundLogger:
    """获取结构化日志实例

    Args:
        name: 日志名称

    Returns:
        BoundLogger: 配置好的 structlog 日志实例
    """
    return structlog.get_logger(name)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话

    Yields:
        AsyncSession: 数据库会话
    """
    async for session in db_get_db():
        yield session


# 默认用户 ID（无需登录模式）
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


# 用户认证依赖（简化版 - 无需登录）
async def get_current_user() -> UUID:
    """获取当前用户 ID（无需登录模式）

    返回固定的默认用户 ID，用于单用户场景。
    生产环境应使用 JWT 验证。

    Returns:
        UUID: 默认用户 ID
    """
    return DEFAULT_USER_ID


async def get_current_user_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> UUID:
    """获取当前用户 ID（JWT 认证模式）

    从 Authorization header 中提取并验证 JWT token。

    Args:
        credentials: HTTP Bearer 认证凭据

    Returns:
        UUID: 当前用户 ID

    Raises:
        HTTPException: 未提供或无效的认证凭据
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from app.services.user_service import UserService

    user_id = UserService.decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UUID(user_id)


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> UUID | None:
    """获取当前用户 ID（可选认证）

    如果提供了有效的 token 则返回用户 ID，否则返回 None。

    Args:
        credentials: HTTP Bearer 认证凭据

    Returns:
        UUID | None: 当前用户 ID 或 None
    """
    if credentials is None:
        return None

    from app.services.user_service import UserService

    user_id = UserService.decode_access_token(credentials.credentials)
    if user_id is None:
        return None

    return UUID(user_id)


# 服务依赖注入
async def get_session_service(
    db: AsyncSession = Depends(get_db),
) -> "SessionService":
    """获取会话服务实例

    Args:
        db: 数据库会话

    Returns:
        SessionService: 会话服务实例
    """
    from app.services.session_service import SessionService

    return SessionService(db)


async def get_model_service(
    db: AsyncSession = Depends(get_db),
) -> "ModelService":
    """获取模型服务实例

    Args:
        db: 数据库会话

    Returns:
        ModelService: 模型服务实例
    """
    from app.services.model_service import ModelService

    return ModelService(db)


async def get_chat_service(
    db: AsyncSession = Depends(get_db),
) -> "ChatService":
    """获取聊天服务实例

    Args:
        db: 数据库会话

    Returns:
        ChatService: 聊天服务实例
    """
    from app.services.chat_service import ChatService

    return ChatService(db)


async def get_file_service(
    db: AsyncSession = Depends(get_db),
) -> "FileService":
    """获取文件服务实例

    Args:
        db: 数据库会话

    Returns:
        FileService: 文件服务实例
    """
    from app.services.file_service import FileService

    return FileService(db)


async def get_batch_service(
    db: AsyncSession = Depends(get_db),
) -> "BatchService":
    """获取批处理服务实例

    Args:
        db: 数据库会话

    Returns:
        BatchService: 批处理服务实例
    """
    from app.services.batch_service import BatchService

    return BatchService(db)


async def get_user_service(
    db: AsyncSession = Depends(get_db),
) -> "UserService":
    """获取用户服务实例

    Args:
        db: 数据库会话

    Returns:
        UserService: 用户服务实例
    """
    from app.services.user_service import UserService

    return UserService(db)


__all__ = [
    "get_settings_dependency",
    "get_logger_dependency",
    "get_db",
    "get_current_user",
    "get_current_user_auth",
    "get_current_user_optional",
    "get_session_service",
    "get_model_service",
    "get_chat_service",
    "get_file_service",
    "get_batch_service",
    "get_user_service",
]
