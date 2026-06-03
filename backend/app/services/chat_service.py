"""
聊天服务

处理聊天请求，管理消息流式响应。
"""

from uuid import UUID
from typing import AsyncIterator, Optional
import base64

from sqlalchemy import select

from .base import BaseService
from .session_service import SessionService
from .model_service import ModelService
from .file_service import FileService
from app.core import (
    BaseLLMAdapter,
    ChatMessage,
    ChatCompletionChunk,
    StreamBuffer,
    LLMException,
    RateLimitError,
)
from app.models.database import Message, MessageRole, ToolExecution, File, FileType
from app.models.schemas import ChatRequest, MessageResponse, MessageCreate


class ChatService(BaseService):
    """聊天服务

    处理聊天请求，协调适配器调用和消息存储。
    """

    def __init__(self, db):
        super().__init__(db)
        self.session_service = SessionService(db)
        self.model_service = ModelService(db)
        self.file_service = None  # 延迟初始化

    # =========================================================================
    # 聊天核心逻辑
    # =========================================================================

    async def chat(
        self,
        session_id: UUID,
        user_id: UUID,
        request: ChatRequest
    ) -> AsyncIterator[ChatCompletionChunk]:
        """流式聊天

        Args:
            session_id: 会话 ID
            user_id: 用户 ID
            request: 聊天请求

        Yields:
            响应块

        Raises:
            ValueError: 会话不存在
            LLMException: LLM 调用失败
        """
        self.logger.info(f"Chat request for session {session_id}")
        print(f"\n{'='*80}\nDEBUG: Chat request for session {session_id}, user {user_id}\n{'='*80}\n", flush=True)

        # 验证会话归属
        session = await self.session_service.get_session(session_id, user_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        print(f"DEBUG: Session found: {session.id}\n", flush=True)

        # 获取会话配置
        config = await self.session_service.get_session_config(session_id)
        if not config:
            raise ValueError(f"Session config not found for {session_id}")
        print(f"DEBUG: Session config found\n", flush=True)

        # 获取适配器
        print(f"DEBUG: Getting adapter for session...\n", flush=True)
        # 如果请求中指定了 model_config_id，则使用该配置，否则使用会话配置或默认配置
        if request.model_config_id:
            adapter = await self.model_service.get_adapter(request.model_config_id, user_id)
            print(f"DEBUG: Using specified model_config_id: {request.model_config_id}\n", flush=True)
        else:
            adapter = await self.model_service.get_adapter_for_session(session_id, user_id)
        print(f"DEBUG: Adapter created: {type(adapter).__name__}, base_url={adapter.base_url}\n", flush=True)

        try:
            # 构建消息历史（优先使用请求中的 system_prompt）
            messages = await self._build_messages(
                session_id,
                request.message,
                request.file_ids,
                request.system_prompt  # 传入请求中的系统指令
            )

            # 保存用户消息
            user_message = await self.session_service.add_message(
                session_id,
                MessageCreate(
                    role=MessageRole.user,
                    content=request.message,
                )
            )

            # 关联文件附件
            if request.file_ids:
                await self._attach_files_to_message(user_message.id, request.file_ids)

            # 流式响应
            buffer = StreamBuffer()
            # 从请求中获取 enable_reasoning 参数（默认为 True）
            enable_reasoning = getattr(request, 'enable_reasoning', True)
            async for chunk in self._stream_response(adapter, messages, config, enable_reasoning):
                buffer.append(chunk)
                yield chunk

            # 保存助手消息
            await self._save_assistant_message(
                session_id,
                buffer.get_content(),
                buffer.get_thinking(),
                buffer.get_usage(),
                buffer.get_tool_calls(),
            )

        except LLMException as e:
            self.logger.error(f"LLM error: {e.error_code} - {e.message}")
            yield ChatCompletionChunk(
                type="error",
                content=None,
                thinking=None,
                tool_call=None,
                usage=None,
                error=e.message,
            )
        finally:
            await adapter.close()

    async def chat_complete(
        self,
        session_id: UUID,
        user_id: UUID,
        request: ChatRequest
    ) -> MessageResponse:
        """非流式聊天

        Args:
            session_id: 会话 ID
            user_id: 用户 ID
            request: 聊天请求

        Returns:
            完整响应

        Raises:
            ValueError: 会话不存在
            LLMException: LLM 调用失败
        """
        # 收集所有流式响应
        buffer = StreamBuffer()
        async for chunk in self.chat(session_id, user_id, request):
            buffer.append(chunk)

        return MessageResponse(
            content=buffer.get_content(),
            thinking=buffer.get_thinking(),
            tool_calls=buffer.get_tool_calls(),
            usage=buffer.get_usage(),
        )

    async def _build_messages(
        self,
        session_id: UUID,
        new_message: str,
        file_ids: Optional[list[UUID]] = None,
        system_prompt: Optional[str] = None  # 请求中的系统指令，优先级更高
    ) -> list[ChatMessage]:
        """构建消息列表

        Args:
            session_id: 会话 ID
            new_message: 新消息内容
            file_ids: 附件文件 ID 列表
            system_prompt: 可选的系统指令（优先于会话配置）

        Returns:
            消息列表
        """
        messages = []

        # 获取会话配置
        config = await self.session_service.get_session_config(session_id)

        # 添加系统提示（优先使用请求中的 system_prompt）
        effective_system_prompt = system_prompt or (config.system_prompt if config else None)
        if effective_system_prompt:
            messages.append(ChatMessage(
                role="system",
                content=effective_system_prompt,
            ))

        # 获取历史消息
        history = await self.session_service.get_messages(session_id, limit=20)
        for msg in reversed(history):
            messages.append(ChatMessage(
                role=msg.role.value,
                content=msg.content,
            ))

        # 处理多模态内容
        if file_ids:
            content_blocks = await self._process_files(file_ids)
            content_blocks.append({
                "type": "text",
                "text": new_message,
            })
            messages.append(ChatMessage(
                role="user",
                content=content_blocks,
            ))
            # 调试日志:打印多模态消息格式
            self.logger.info(f"Multimodal message with {len(file_ids)} files")
            print(f"\n{'='*80}\nDEBUG: Multimodal message content:\n{content_blocks}\n{'='*80}\n", flush=True)
        else:
            messages.append(ChatMessage(
                role="user",
                content=new_message,
            ))

        return messages

    async def _process_files(
        self,
        file_ids: list[UUID]
    ) -> list[dict]:
        """处理文件为多模态内容块

        Args:
            file_ids: 文件 ID 列表

        Returns:
            内容块列表
        """
        if not self.file_service:
            from .file_service import FileService
            self.file_service = FileService(self.db)

        content_blocks = []

        for file_id in file_ids:
            try:
                # 获取文件信息（不需要 user_id，因为已经在会话上下文中验证过）
                stmt = select(File).where(File.id == str(file_id))
                result = await self.db.execute(stmt)
                file = result.scalar_one_or_none()

                if not file:
                    self.logger.warning(f"File not found: {file_id}")
                    continue

                # 根据文件类型创建内容块
                if file.type == FileType.image:
                    # 按照OpenAI/Qwen多模态API格式
                    content_blocks.append({
                        "type": "image_url",
                        "image_url": {
                            "url": file.url
                        },
                    })
                # 可以扩展支持其他类型（音频、视频等）
                # elif file.file_type == FileType.audio:
                #     content_blocks.append({
                #         "type": "audio",
                #         "audio_url": file.url,
                #     })

            except Exception as e:
                self.logger.error(f"Error processing file {file_id}: {e}")
                continue

        return content_blocks

    async def _attach_files_to_message(
        self,
        message_id: str,
        file_ids: list[UUID]
    ) -> None:
        """关联文件到消息

        Args:
            message_id: 消息 ID
            file_ids: 文件 ID 列表
        """
        from app.models.database import MessageAttachment

        for file_id in file_ids:
            attachment = MessageAttachment(
                message_id=message_id,
                file_id=str(file_id),
            )
            self.db.add(attachment)

        await self.db.commit()

    # =========================================================================
    # 流式响应处理
    # =========================================================================

    async def _stream_response(
        self,
        adapter: BaseLLMAdapter,
        messages: list[ChatMessage],
        config,
        enable_reasoning: bool = True
    ) -> AsyncIterator[ChatCompletionChunk]:
        """处理流式响应

        Args:
            adapter: LLM 适配器
            messages: 消息列表
            config: 会话配置
            enable_reasoning: 是否启用推理模式

        Yields:
            响应块
        """
        try:
            # 传递 enable_reasoning 参数以启用推理模式
            # OpenRouter 需要此参数通过 extra_body 启用 reasoning
            response = await adapter.chat_completion(
                messages=messages,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                stream=True,
                enable_reasoning=enable_reasoning,  # 根据参数决定是否启用推理模式
            )

            async for chunk in response:
                yield chunk

        except RateLimitError as e:
            self.logger.warning(f"Rate limit: {e.retry_after}s")
            raise
        except LLMException as e:
            self.logger.error(f"LLM error: {e.error_code}")
            raise

    async def _save_assistant_message(
        self,
        session_id: UUID,
        content: str,
        thinking: Optional[str],
        usage: Optional[dict],
        tool_calls: Optional[list]
    ) -> Message:
        """保存助手消息

        Args:
            session_id: 会话 ID
            content: 消息内容
            thinking: 思考内容
            usage: Token 使用统计
            tool_calls: 工具调用列表

        Returns:
            创建的消息对象
        """
        token_count = None
        if usage:
            token_count = usage.get("total_tokens")

        message = await self.session_service.add_message(
            session_id,
            MessageCreate(
                role=MessageRole.assistant,
                content=content,
                thinking_content=thinking,
                token_count=token_count,
            )
        )

        # 处理工具调用
        if tool_calls:
            await self._handle_tool_calls(message.id, tool_calls)

        return message

    # =========================================================================
    # 工具调用处理
    # =========================================================================

    async def _handle_tool_calls(
        self,
        message_id: UUID,
        tool_calls: list[dict]
    ) -> list[ToolExecution]:
        """处理工具调用

        Args:
            message_id: 消息 ID
            tool_calls: 工具调用列表

        Returns:
            工具执行记录列表
        """
        # TODO: 实际执行在 Phase 6 实现
        executions = []

        for tool_call in tool_calls:
            execution = ToolExecution(
                message_id=str(message_id),
                tool_name=tool_call.get("function", {}).get("name"),
                tool_input=tool_call.get("function", {}).get("arguments"),
                status="pending",
            )
            self.db.add(execution)
            executions.append(execution)

        await self.db.commit()
        return executions


# 导入辅助类型
from app.models.schemas import MessageCreate
