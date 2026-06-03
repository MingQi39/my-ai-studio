"""
OpenAI 兼容适配器基类

适用于所有兼容 OpenAI API 格式的官方直连供应商。
子类只需覆写特殊功能的处理逻辑。
"""

from typing import AsyncIterator, Any

from openai import AsyncOpenAI, APIError, AuthenticationError as OpenAIAuthError

from ..base import BaseLLMAdapter
from ..types import (
    ChatMessage,
    ChatCompletionChunk,
    ModelInfo,
    ChatCompletionResponse,
)
from ...exceptions import (
    LLMException,
    AuthenticationError,
    RateLimitError,
    InsufficientBalanceError,
    ModelUnavailableError,
    ProviderConnectionError,
    ProviderTimeoutError,
)


class OpenAICompatibleAdapter(BaseLLMAdapter):
    """OpenAI 兼容 API 适配器基类

    适用于所有兼容 OpenAI API 格式的官方直连供应商。
    子类只需覆写特殊功能的处理逻辑。
    """

    PROVIDER: str = "openai_compatible"
    DEFAULT_BASE_URL: str = ""
    SUPPORTED_MODELS: dict[str, ModelInfo] = {}

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model_id: str = "",
        timeout: int = 120,
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url or self.DEFAULT_BASE_URL,
            model_id=model_id,
            timeout=timeout
        )
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=self.base_url,
            timeout=timeout
        )

    async def chat_completion(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float | None = None,
        stream: bool = True,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> AsyncIterator[ChatCompletionChunk] | ChatCompletionResponse:
        """通用聊天补全实现"""
        request_params = self._build_request_params(
            messages, temperature, max_tokens, top_p, stream, tools, **kwargs
        )

        try:
            response = await self._client.chat.completions.create(**request_params)

            if stream:
                return self._handle_stream_response(response)
            else:
                return self._handle_response(response)
        except Exception as e:
            raise self._handle_error(e)

    def _build_request_params(
        self,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int | None,
        top_p: float | None,
        stream: bool,
        tools: list[dict] | None,
        **kwargs,
    ) -> dict:
        """构建请求参数，子类可覆写以添加特殊参数"""
        params: dict[str, Any] = {
            "model": self.model_id,
            "messages": self._convert_messages(messages),
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if top_p is not None:
            params["top_p"] = top_p
        if tools:
            params["tools"] = tools
        return params

    def _convert_messages(self, messages: list[ChatMessage]) -> list[dict]:
        """转换消息格式为 OpenAI 格式，子类可覆写"""
        converted = [dict(msg) for msg in messages]
        # 调试日志:打印发送给API的消息
        print(f"\n{'='*80}\nDEBUG: Messages sent to API:\n", flush=True)
        for i, msg in enumerate(converted):
            print(f"Message {i}: role={msg.get('role')}, content_type={type(msg.get('content'))}", flush=True)
            if isinstance(msg.get('content'), list):
                print(f"  Content blocks: {len(msg.get('content'))} items", flush=True)
                for j, block in enumerate(msg.get('content')):
                    if isinstance(block, dict):
                        block_type = block.get('type')
                        print(f"    Block {j}: type={block_type}", flush=True)
                        if block_type == 'image_url':
                            url = block.get('image_url', {}).get('url', '')
                            url_preview = url[:100] + '...' if len(url) > 100 else url
                            print(f"      URL: {url_preview}", flush=True)
                        elif block_type == 'text':
                            print(f"      Text: {block.get('text', '')[:50]}...", flush=True)
        print(f"{'='*80}\n", flush=True)
        return converted

    async def _handle_stream_response(
        self, response: Any
    ) -> AsyncIterator[ChatCompletionChunk]:
        """处理流式响应，子类可覆写以处理特殊字段"""
        async for chunk in response:
            parsed = self._parse_chunk(chunk)
            if parsed is not None:
                yield parsed

    def _parse_chunk(self, chunk: Any) -> ChatCompletionChunk | None:
        """解析响应块，子类可覆写以处理特殊字段"""
        if not chunk.choices:
            # 可能是 usage 信息
            if hasattr(chunk, 'usage') and chunk.usage:
                return ChatCompletionChunk(
                    type="usage",
                    content=None,
                    thinking=None,
                    tool_call=None,
                    usage=chunk.usage.model_dump() if hasattr(chunk.usage, 'model_dump') else dict(chunk.usage),
                    error=None,
                )
            return None

        choice = chunk.choices[0]
        delta = choice.delta
        finish_reason = choice.finish_reason

        # 完成信号
        if finish_reason:
            return ChatCompletionChunk(
                type="done",
                content=None,
                thinking=None,
                tool_call=None,
                usage=None,
                error=None,
            )

        # 工具调用
        if hasattr(delta, 'tool_calls') and delta.tool_calls:
            tool_call = delta.tool_calls[0]
            return ChatCompletionChunk(
                type="tool_call",
                content=None,
                thinking=None,
                tool_call=tool_call.model_dump() if hasattr(tool_call, 'model_dump') else dict(tool_call),
                usage=None,
                error=None,
            )

        # 文本内容
        if hasattr(delta, 'content') and delta.content:
            return ChatCompletionChunk(
                type="content",
                content=delta.content,
                thinking=None,
                tool_call=None,
                usage=None,
                error=None,
            )

        return None

    def _handle_response(self, response: Any) -> ChatCompletionResponse:
        """处理非流式响应"""
        message = response.choices[0].message
        return ChatCompletionResponse(
            content=message.content,
            reasoning_content=None,
            tool_calls=[tc.model_dump() for tc in message.tool_calls] if message.tool_calls else None,
            usage=response.usage.model_dump() if response.usage else None,
            model=response.model,
            finish_reason=response.choices[0].finish_reason,
        )

    def _handle_error(self, error: Exception) -> LLMException:
        """错误处理，子类可覆写"""
        if isinstance(error, OpenAIAuthError):
            return AuthenticationError(provider=self.PROVIDER)

        if isinstance(error, APIError):
            status_code = getattr(error, 'status_code', 500)
            if status_code == 429:
                retry_after = 60
                if hasattr(error, 'response') and error.response:
                    retry_after = int(error.response.headers.get("Retry-After", 60))
                return RateLimitError(retry_after=retry_after)
            elif status_code == 402:
                return InsufficientBalanceError(provider=self.PROVIDER)
            elif status_code == 503:
                return ModelUnavailableError(
                    model_id=self.model_id,
                    reason="Service unavailable"
                )
            elif status_code == 504:
                return ProviderTimeoutError(timeout_seconds=self.timeout)

        if isinstance(error, LLMException):
            return error

        # Log the original error for debugging  
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        error_msg = f"Unexpected error in adapter: {str(error)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        print(f"\n{'='*80}\nDEBUG ERROR:\n{error_msg}\n{'='*80}\n", flush=True)

        return ProviderConnectionError(
            provider=self.PROVIDER,
            endpoint=self.base_url
        )

    async def list_models(self) -> list[ModelInfo]:
        """列出可用模型"""
        return list(self.SUPPORTED_MODELS.values())

    async def validate_credentials(self) -> bool:
        """验证凭证"""
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False

    def supports_feature(self, feature: str) -> bool:
        """检查功能支持"""
        model_info = self.SUPPORTED_MODELS.get(self.model_id)
        if not model_info:
            return feature == "streaming"

        feature_map = {
            "vision": model_info.get("supports_vision", False),
            "tools": model_info.get("supports_tools", False),
            "reasoning": model_info.get("supports_reasoning", False),
            "audio": model_info.get("supports_audio", False),
            "streaming": True,
        }
        return feature_map.get(feature, False)

    async def close(self) -> None:
        """关闭连接"""
        if self._client is not None:
            await self._client.close()
            self._client = None
