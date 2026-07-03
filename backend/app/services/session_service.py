"""
会话服务

提供会话、会话配置和消息的 CRUD 操作。
"""

from uuid import UUID
from typing import Optional
from datetime import datetime

from sqlalchemy import select, and_, desc, func
from sqlalchemy.orm import selectinload

from .base import BaseService
from app.models.database import Session, SessionConfig, Message, MessageAttachment, SessionType
from app.models.schemas import (
    SessionCreate,
    SessionUpdate,
    SessionConfigUpdate,
    MessageCreate,
    PaginationParams,
    PaginatedResponse,
    SessionResponse,
    ChatToolsConfig,
)


class SessionService(BaseService):
    """会话服务

    管理会话、会话配置和消息。
    """

    # =========================================================================
    # 会话 CRUD
    # =========================================================================

    async def create_session(
        self,
        user_id: UUID,
        data: SessionCreate
    ) -> Session:
        """创建会话

        Args:
            user_id: 用户 ID
            data: 会话创建数据

        Returns:
            创建的会话对象
        """
        self.logger.info(f"Creating session for user {user_id}")

        # 创建会话记录
        session = Session(
            user_id=str(user_id),  # 将 UUID 转换为字符串
            title=data.title or "New Chat",
            description=data.description,
            session_type=data.session_type,
        )
        self.db.add(session)
        await self.db.flush()

        # 创建默认会话配置（使用默认值）
        config = SessionConfig(
            session_id=session.id,
            model_id="gpt-4",  # 默认模型
            temperature=0.7,   # 默认温度 (0.0-2.0 for most models)
            max_tokens=None,
            top_p=None,
            system_prompt=None,
        )
        self.db.add(config)

        await self.db.commit()
        await self.db.refresh(session)

        self.logger.info(f"Session created: {session.id}")
        return session

    async def get_session(
        self,
        session_id: UUID,
        user_id: UUID
    ) -> Optional[Session]:
        """获取会话

        Args:
            session_id: 会话 ID
            user_id: 用户 ID

        Returns:
            会话对象或 None
        """
        stmt = (
            select(Session)
            .where(
                and_(
                    Session.id == str(session_id),
                    Session.user_id == str(user_id)
                )
            )
            .options(
                selectinload(Session.messages),
                selectinload(Session.config)
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_sessions(
        self,
        user_id: UUID,
        params: PaginationParams,
        include_archived: bool = False,
        session_type: SessionType | None = SessionType.chat,
    ) -> PaginatedResponse[SessionResponse]:
        """列出会话

        Args:
            user_id: 用户 ID
            params: 分页参数
            include_archived: 是否包含已归档会话
            session_type: 会话类型过滤；None 表示不过滤

        Returns:
            分页响应
        """
        # 构建查询
        conditions = [Session.user_id == str(user_id)]
        if not include_archived:
            conditions.append(Session.is_archived == False)
        if session_type is not None:
            conditions.append(Session.session_type == session_type)

        # 计数查询
        count_stmt = select(Session).where(and_(*conditions))
        count_result = await self.db.execute(count_stmt)
        total = len(count_result.scalars().all())

        # 数据查询
        offset = (params.page - 1) * params.page_size
        stmt = (
            select(Session)
            .where(and_(*conditions))
            .order_by(desc(Session.created_at))
            .offset(offset)
            .limit(params.page_size)
        )
        result = await self.db.execute(stmt)
        items = result.scalars().all()

        # 为每个会话计算消息数量
        session_responses: list[SessionResponse] = []
        for session in items:
            # 查询该会话的消息数量
            msg_count_stmt = select(func.count(Message.id)).where(Message.session_id == str(session.id))
            msg_count_result = await self.db.execute(msg_count_stmt)
            message_count = msg_count_result.scalar() or 0
            
            # 创建SessionResponse并设置message_count
            session_response = SessionResponse.from_orm(session)
            session_response.message_count = message_count
            session_responses.append(session_response)

        total_pages = (total + params.page_size - 1) // params.page_size

        return PaginatedResponse(
            items=session_responses,
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=total_pages,
        )

    async def update_session(
        self,
        session_id: UUID,
        user_id: UUID,
        data: SessionUpdate
    ) -> Session:
        """更新会话

        Args:
            session_id: 会话 ID
            user_id: 用户 ID
            data: 更新数据

        Returns:
            更新后的会话对象

        Raises:
            ValueError: 会话不存在
        """
        session = await self.get_session(session_id, user_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # 更新字段
        if data.title is not None:
            session.title = data.title
        if data.description is not None:
            session.description = data.description
        if data.is_archived is not None:
            session.is_archived = data.is_archived

        session.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(session)

        self.logger.info(f"Session updated: {session_id}")
        return session

    async def delete_session(
        self,
        session_id: UUID,
        user_id: UUID
    ) -> bool:
        """删除会话

        Args:
            session_id: 会话 ID
            user_id: 用户 ID

        Returns:
            是否删除成功
        """
        session = await self.get_session(session_id, user_id)
        if not session:
            return False

        await self.db.delete(session)
        await self.db.commit()

        self.logger.info(f"Session deleted: {session_id}")
        return True

    async def archive_session(
        self,
        session_id: UUID,
        user_id: UUID
    ) -> Session:
        """归档会话

        Args:
            session_id: 会话 ID
            user_id: 用户 ID

        Returns:
            归档后的会话对象
        """
        session = await self.get_session(session_id, user_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.is_archived = True
        session.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(session)

        self.logger.info(f"Session archived: {session_id}")
        return session

    # =========================================================================
    # 会话配置
    # =========================================================================

    async def get_session_config(
        self,
        session_id: UUID
    ) -> Optional[SessionConfig]:
        """获取会话配置

        Args:
            session_id: 会话 ID

        Returns:
            会话配置或 None
        """
        stmt = select(SessionConfig).where(SessionConfig.session_id == str(session_id))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_session_config(
        self,
        session_id: UUID,
        user_id: UUID,
        data: SessionConfigUpdate
    ) -> SessionConfig:
        """更新会话配置

        Args:
            session_id: 会话 ID
            user_id: 用户 ID
            data: 配置更新数据

        Returns:
            更新后的配置对象

        Raises:
            ValueError: 会话不存在或配置不存在
        """
        # 验证会话归属
        session = await self.get_session(session_id, user_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # 获取配置
        config = await self.get_session_config(session_id)
        if not config:
            raise ValueError(f"Config for session {session_id} not found")

        # 更新字段
        # TODO: 需要验证 adapter_type、provider 和 model_id 有效性
        if data.model_id is not None:
            config.model_id = data.model_id
        if data.temperature is not None:
            config.temperature = data.temperature
        if data.max_tokens is not None:
            config.max_tokens = data.max_tokens
        if data.top_p is not None:
            config.top_p = data.top_p
        if data.system_prompt is not None:
            config.system_prompt = data.system_prompt
        if data.tools_config is not None:
            config.tools_config = data.tools_config.model_dump()

        await self.db.commit()
        await self.db.refresh(config)

        self.logger.info(f"Session config updated: {session_id}")
        return config

    async def save_tools_config(
        self,
        session_id: UUID,
        user_id: UUID,
        tools_config: ChatToolsConfig,
    ) -> None:
        """Persist enabled chat tools for a session."""
        session = await self.get_session(session_id, user_id)
        if not session:
            return

        config = await self.get_session_config(session_id)
        if not config:
            return

        config.tools_config = tools_config.model_dump()
        await self.db.commit()

    # =========================================================================
    # 消息管理
    # =========================================================================

    async def add_message(
        self,
        session_id: UUID,
        data: MessageCreate
    ) -> Message:
        """添加消息

        Args:
            session_id: 会话 ID
            data: 消息创建数据

        Returns:
            创建的消息对象
        """
        message = Message(
            session_id=str(session_id),
            role=data.role,
            content=data.content,
            thinking_content=data.thinking_content,
            tokens_used=data.token_count,
            tool_calls=data.tool_calls,
            is_complete=getattr(data, "is_complete", True),
        )
        self.db.add(message)

        # 更新会话 updated_at
        stmt = select(Session).where(Session.id == str(session_id))
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()
        if session:
            session.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(message)

        self.logger.info(f"Message added to session {session_id}")
        return message

    async def get_messages(
        self,
        session_id: UUID,
        limit: int = 50,
        before_id: Optional[UUID] = None
    ) -> list[Message]:
        """获取会话消息历史

        Args:
            session_id: 会话 ID
            limit: 返回数量限制
            before_id: 游标 ID（返回此 ID 之前的消息）

        Returns:
            消息列表
        """
        conditions = [Message.session_id == str(session_id)]
        if before_id:
            conditions.append(Message.id < str(before_id))

        from sqlalchemy.orm import selectinload
        stmt = (
            select(Message)
            .where(and_(*conditions))
            .options(
                selectinload(Message.attachments).selectinload(MessageAttachment.file),
                selectinload(Message.tool_executions),
            )
            .order_by(desc(Message.created_at))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_message(
        self,
        message_id: UUID
    ) -> Optional[Message]:
        """获取单条消息

        Args:
            message_id: 消息 ID

        Returns:
            消息对象或 None
        """
        stmt = (
            select(Message)
            .where(Message.id == str(message_id))
            .options(selectinload(Message.tool_executions))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_message(
        self,
        session_id: UUID,
        message_id: UUID,
        user_id: UUID,
    ) -> bool:
        """删除会话中的单条消息（需验证会话归属）"""
        session = await self.get_session(session_id, user_id)
        if not session:
            return False

        stmt = select(Message).where(
            and_(
                Message.id == str(message_id),
                Message.session_id == str(session_id),
            )
        )
        result = await self.db.execute(stmt)
        message = result.scalar_one_or_none()
        if not message:
            return False

        await self.db.delete(message)
        await self.db.commit()
        return True
