"""
聊天服务

处理聊天请求，管理消息流式响应与工具调用。
"""

from __future__ import annotations

import json
import time
from uuid import UUID
from typing import AsyncIterator, Optional, Any

from sqlalchemy import select

from .base import BaseService
from .session_service import SessionService
from .model_service import ModelService
from .file_service import FileService
from app.services.chat_tools.resolve import resolve_tool_calls
from app.services.chat_tools import build_tools_and_format, tool_type_for_name
from app.services.chat_tools.builder import adapt_response_format, STRUCTURED_JSON_HINT
from app.services.chat_tools.handlers import today_date_hint
from app.core.adapters.message_utils import sanitize_messages_for_api
from app.core import (
    BaseLLMAdapter,
    ChatMessage,
    ChatCompletionChunk,
    StreamBuffer,
    LLMException,
    RateLimitError,
)
from app.models.database import (
    Message,
    MessageRole,
    ToolExecution,
    ToolExecutionStatus,
    ToolType,
    File,
    FileType,
)
from app.models.schemas import ChatRequest, MessageResponse, MessageCreate


MAX_TOOL_ROUNDS = 5


class ChatService(BaseService):
    """聊天服务

    处理聊天请求，协调适配器调用和消息存储。
    """

    def __init__(self, db):
        super().__init__(db)
        self.session_service = SessionService(db)
        self.model_service = ModelService(db)
        self.file_service = None  # 延迟初始化

    async def chat(
        self,
        session_id: UUID,
        user_id: UUID,
        request: ChatRequest,
    ) -> AsyncIterator[ChatCompletionChunk]:
        """流式聊天（支持工具多轮调用）"""
        self.logger.info(f"Chat request for session {session_id}")

        session = await self.session_service.get_session(session_id, user_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        config = await self.session_service.get_session_config(session_id)
        if not config:
            raise ValueError(f"Session config not found for {session_id}")

        if request.model_config_id:
            adapter = await self.model_service.get_adapter(request.model_config_id, user_id)
        else:
            adapter = await self.model_service.get_adapter_for_session(session_id, user_id)

        tools_config = request.tools_config
        openai_tools, response_format, tool_registry = build_tools_and_format(tools_config)
        has_tools = len(openai_tools) > 0
        provider = getattr(adapter, "PROVIDER", None)
        api_response_format = adapt_response_format(response_format, provider)
        wants_structured = api_response_format is not None
        structured_with_tools = wants_structured and has_tools

        enable_reasoning = getattr(request, "enable_reasoning", True)
        # 工具调用与 DeepSeek 思考模式不兼容，启用工具时关闭思考
        if has_tools or wants_structured:
            enable_reasoning = False
        execution_log: list[dict[str, Any]] = []

        try:
            messages: list[ChatMessage] = await self._build_messages(
                session_id,
                request.message,
                request.file_ids,
                request.system_prompt,
                tools_config,
            )

            user_message = await self.session_service.add_message(
                session_id,
                MessageCreate(role=MessageRole.user, content=request.message),
            )

            if request.file_ids:
                await self._attach_files_to_message(user_message.id, request.file_ids)

            final_content = ""
            final_thinking = ""
            final_tool_calls: list[dict] | None = None
            final_usage: dict | None = None

            for round_idx in range(MAX_TOOL_ROUNDS):
                buffer = StreamBuffer()
                async for chunk in self._stream_response(
                    adapter,
                    messages,
                    config,
                    enable_reasoning,
                    tools=openai_tools if has_tools else None,
                    response_format=api_response_format if not has_tools else None,
                ):
                    buffer.append(chunk)
                    if chunk["type"] in ("content", "thinking", "tool_call"):
                        if structured_with_tools and chunk["type"] == "content":
                            continue
                        yield chunk

                final_usage = buffer.get_usage() or final_usage

                if has_tools and buffer.has_tool_calls():
                    raw_tool_calls = resolve_tool_calls(
                        buffer.get_tool_calls(), tool_registry
                    )
                    tool_calls = sanitize_messages_for_api(
                        [{"role": "assistant", "tool_calls": raw_tool_calls, "content": ""}]
                    )[0]["tool_calls"]
                    assistant_text = buffer.get_content() or ""
                    round_thinking = buffer.get_thinking() or ""

                    assistant_msg: ChatMessage = {
                        "role": "assistant",
                        "content": assistant_text,
                        "tool_calls": tool_calls,
                    }
                    if round_thinking:
                        assistant_msg["reasoning_content"] = round_thinking
                    messages.append(assistant_msg)

                    for tc in tool_calls:
                        func = tc.get("function") or {}
                        name = func.get("name") or ""
                        args_raw = func.get("arguments") or "{}"
                        call_id = tc.get("id") or f"call_{round_idx}_{name}"

                        try:
                            args = json.loads(args_raw) if args_raw else {}
                        except json.JSONDecodeError:
                            args = {}

                        yield ChatCompletionChunk(
                            type="tool_result",
                            content=None,
                            thinking=None,
                            tool_call=None,
                            tool_result={
                                "tool_name": name,
                                "tool_type": tool_type_for_name(name),
                                "tool_input": args,
                                "status": "running",
                            },
                            usage=None,
                            error=None,
                        )

                        started = time.perf_counter()
                        try:
                            output = await tool_registry.execute(name, args)
                            ok = True
                            err = None
                        except Exception as exc:  # noqa: BLE001
                            output = json.dumps({"error": str(exc)}, ensure_ascii=False)
                            ok = False
                            err = str(exc)

                        elapsed_ms = int((time.perf_counter() - started) * 1000)
                        execution_log.append(
                            {
                                "name": name,
                                "tool_type": tool_type_for_name(name),
                                "input": args,
                                "output": output,
                                "ok": ok,
                                "error": err,
                                "ms": elapsed_ms,
                            }
                        )

                        yield ChatCompletionChunk(
                            type="tool_result",
                            content=None,
                            thinking=None,
                            tool_call=None,
                            tool_result={
                                "tool_name": name,
                                "tool_type": tool_type_for_name(name),
                                "tool_input": args,
                                "tool_output": output,
                                "status": "completed" if ok else "error",
                                "duration_ms": elapsed_ms,
                            },
                            usage=None,
                            error=None,
                        )

                        messages.append(
                            ChatMessage(
                                role="tool",
                                tool_call_id=call_id,
                                content=output,
                            )
                        )

                    continue

                final_content = buffer.get_content()
                final_thinking = buffer.get_thinking() or final_thinking
                final_tool_calls = buffer.get_tool_calls() or None
                break

            if structured_with_tools:
                buffer = StreamBuffer()
                async for chunk in self._stream_response(
                    adapter,
                    messages,
                    config,
                    enable_reasoning,
                    tools=None,
                    response_format=api_response_format,
                ):
                    buffer.append(chunk)
                    if chunk["type"] in ("content", "thinking", "tool_call"):
                        yield chunk
                final_content = buffer.get_content()
                final_thinking = buffer.get_thinking() or final_thinking
                final_usage = buffer.get_usage() or final_usage
                final_tool_calls = None

            await self._save_assistant_message(
                session_id,
                final_content,
                final_thinking,
                final_usage,
                final_tool_calls,
                execution_log,
            )

        except LLMException as e:
            self.logger.error(f"LLM error: {e.error_code} - {e.message}")
            yield ChatCompletionChunk(
                type="error",
                content=None,
                thinking=None,
                tool_call=None,
                error=e.message,
            )
        finally:
            await adapter.close()

    async def chat_complete(
        self,
        session_id: UUID,
        user_id: UUID,
        request: ChatRequest,
    ) -> MessageResponse:
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
        system_prompt: Optional[str] = None,
        tools_config=None,
    ) -> list[ChatMessage]:
        messages: list[ChatMessage] = []
        config = await self.session_service.get_session_config(session_id)

        effective_system_prompt = system_prompt or (config.system_prompt if config else None)
        tool_hints: list[str] = []
        if tools_config:
            if tools_config.search:
                today = today_date_hint()
                tool_hints.append(
                    f"Current date: {today} (Asia/Shanghai). "
                    f"When calling web_search for time-sensitive topics (today, latest, scores), "
                    f"always include this date and year {today[:4]} in the query—never use outdated years."
                )
            if tools_config.code:
                tool_hints.append("You may call execute_python to run Python code.")
            if tools_config.function:
                tool_hints.append("You may call calculate or get_current_time when helpful.")
            if tools_config.structured:
                tool_hints.append(STRUCTURED_JSON_HINT)

        if effective_system_prompt or tool_hints:
            combined = effective_system_prompt or ""
            if tool_hints:
                hints = "\n".join(tool_hints)
                combined = f"{combined}\n\n{hints}".strip() if combined else hints
            messages.append(ChatMessage(role="system", content=combined))

        history = await self.session_service.get_messages(session_id, limit=20)
        for msg in reversed(history):
            messages.append(
                ChatMessage(role=msg.role.value, content=msg.content)
            )

        if file_ids:
            content_blocks = await self._process_files(file_ids)
            content_blocks.append({"type": "text", "text": new_message})
            messages.append(ChatMessage(role="user", content=content_blocks))
        else:
            messages.append(ChatMessage(role="user", content=new_message))

        return messages

    async def _process_files(self, file_ids: list[UUID]) -> list[dict]:
        if not self.file_service:
            from .file_service import FileService

            self.file_service = FileService(self.db)

        content_blocks = []
        for file_id in file_ids:
            try:
                stmt = select(File).where(File.id == str(file_id))
                result = await self.db.execute(stmt)
                file = result.scalar_one_or_none()
                if not file:
                    continue
                if file.type == FileType.image:
                    content_blocks.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": file.url},
                        }
                    )
            except Exception as e:
                self.logger.error(f"Error processing file {file_id}: {e}")
        return content_blocks

    async def _attach_files_to_message(
        self,
        message_id: str,
        file_ids: list[UUID],
    ) -> None:
        from app.models.database import MessageAttachment

        for file_id in file_ids:
            attachment = MessageAttachment(
                message_id=message_id,
                file_id=str(file_id),
            )
            self.db.add(attachment)
        await self.db.commit()

    async def _stream_response(
        self,
        adapter: BaseLLMAdapter,
        messages: list[ChatMessage],
        config,
        enable_reasoning: bool = True,
        tools: list[dict] | None = None,
        response_format: dict | None = None,
    ) -> AsyncIterator[ChatCompletionChunk]:
        try:
            response = await adapter.chat_completion(
                messages=messages,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                stream=True,
                tools=tools,
                enable_reasoning=enable_reasoning,
                response_format=response_format,
            )
            async for chunk in response:
                yield chunk
        except RateLimitError:
            raise
        except LLMException:
            raise

    async def _save_assistant_message(
        self,
        session_id: UUID,
        content: str,
        thinking: Optional[str],
        usage: Optional[dict],
        tool_calls: Optional[list],
        execution_log: list[dict[str, Any]],
    ) -> Message:
        token_count = usage.get("total_tokens") if usage else None

        message = await self.session_service.add_message(
            session_id,
            MessageCreate(
                role=MessageRole.assistant,
                content=content or "",
                thinking_content=thinking,
                token_count=token_count,
                tool_calls=tool_calls,
            ),
        )

        for ex in execution_log:
            type_key = ex.get("tool_type", "function")
            try:
                tool_type = ToolType(type_key)
            except ValueError:
                tool_type = ToolType.function

            record = ToolExecution(
                message_id=str(message.id),
                tool_name=ex["name"],
                tool_type=tool_type,
                input_params=ex["input"],
                output=ex.get("output"),
                status=ToolExecutionStatus.completed if ex.get("ok") else ToolExecutionStatus.failed,
                error_message=ex.get("error"),
                execution_time_ms=ex.get("ms"),
            )
            self.db.add(record)

        if execution_log:
            await self.db.commit()

        return message
