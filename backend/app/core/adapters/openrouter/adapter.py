"""
OpenRouter 适配器

通过 OpenRouter 统一网关访问多家模型提供商。
按模态划分：文本、视觉、音频。
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
from ..message_utils import sanitize_messages_for_api
from ...exceptions import (
    LLMException,
    AuthenticationError,
    RateLimitError,
    InsufficientBalanceError,
    ModelUnavailableError,
    ProviderConnectionError,
    ProviderTimeoutError,
)


class OpenRouterAdapter(BaseLLMAdapter):
    """OpenRouter API 适配器

    支持通过单一 API Key 访问多家模型提供商。

    特殊功能：
    - 推理模式：通过 extra_body={"reasoning": {"enabled": True}} 启用
    - 多轮推理：需保留 reasoning_details 传回
    - 图像生成：通过 extra_body={"modalities": ["image", "text"]} 启用
    - 动态模型切换：switch_model(model_id) 方法
    """

    PROVIDER = "openrouter"
    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

    # 模型能力映射（常用模型）
    MODEL_CAPABILITIES: dict[str, dict] = {
        "google/gemini-2.5-pro-preview": {
            "supports_vision": True,
            "supports_tools": True,
            "supports_reasoning": True,
            "supports_image_generation": False,
        },
        "google/gemini-2.0-flash-001": {
            "supports_vision": True,
            "supports_tools": True,
            "supports_reasoning": False,
            "supports_image_generation": False,
        },
        "google/gemini-2.0-flash-exp:free": {
            "supports_vision": True,
            "supports_tools": True,
            "supports_reasoning": False,
            "supports_image_generation": True,
        },
        "openai/gpt-4o": {
            "supports_vision": True,
            "supports_tools": True,
            "supports_reasoning": False,
            "supports_image_generation": False,
        },
        "openai/gpt-4o-mini": {
            "supports_vision": True,
            "supports_tools": True,
            "supports_reasoning": False,
            "supports_image_generation": False,
        },
        "anthropic/claude-3.5-sonnet": {
            "supports_vision": True,
            "supports_tools": True,
            "supports_reasoning": False,
            "supports_image_generation": False,
        },
        "anthropic/claude-3.5-haiku": {
            "supports_vision": True,
            "supports_tools": True,
            "supports_reasoning": False,
            "supports_image_generation": False,
        },
        "meta-llama/llama-3.3-70b-instruct": {
            "supports_vision": False,
            "supports_tools": True,
            "supports_reasoning": False,
            "supports_image_generation": False,
        },
        "deepseek/deepseek-chat": {
            "supports_vision": False,
            "supports_tools": True,
            "supports_reasoning": True,
            "supports_image_generation": False,
        },
    }

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model_id: str = "google/gemini-2.0-flash-001",
        timeout: int = 120,
        enable_reasoning: bool = False,
        modalities: list[str] | None = None,
    ):
        """初始化 OpenRouter 适配器

        Args:
            api_key: OpenRouter API Key
            base_url: API 基础 URL
            model_id: 模型 ID（格式：provider/model-name）
            timeout: 请求超时时间（秒）
            enable_reasoning: 是否启用推理模式
            modalities: 输出模态列表，如 ["image", "text"]
        """
        super().__init__(
            api_key=api_key,
            base_url=base_url or self.DEFAULT_BASE_URL,
            model_id=model_id,
            timeout=timeout
        )
        self.enable_reasoning = enable_reasoning
        self.modalities = modalities
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
        """聊天补全实现"""
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
        """构建请求参数"""
        params: dict[str, Any] = {
            "model": self.model_id,
            "messages": self._sanitize_messages(messages),
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if top_p is not None:
            params["top_p"] = top_p
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        response_format = kwargs.get("response_format")
        if response_format:
            params["response_format"] = response_format

        extra_body: dict[str, Any] = {}

        # 推理模式（与 tools 同时开启时部分模型会报错）
        enable_reasoning = kwargs.get("enable_reasoning", self.enable_reasoning)
        if enable_reasoning and not tools:
            extra_body["reasoning"] = {"enabled": True}

        # 输出模态（图像生成）
        modalities = kwargs.get("modalities", self.modalities)
        if modalities:
            extra_body["modalities"] = modalities

        if extra_body:
            params["extra_body"] = extra_body

        return params

    @staticmethod
    def _sanitize_messages(messages: list[ChatMessage]) -> list[dict]:
        return sanitize_messages_for_api(messages)

    async def _handle_stream_response(
        self, response: Any
    ) -> AsyncIterator[ChatCompletionChunk]:
        """处理流式响应"""
        async for chunk in response:
            parsed = self._parse_chunk(chunk)
            if parsed is not None:
                yield parsed

    def _parse_chunk(self, chunk: Any) -> ChatCompletionChunk | None:
        """解析响应块
        
        注意：OpenRouter 在流式模式下不分离 reasoning，所有内容都在 content 中。
        """
        if not chunk.choices:
            # 可能是 usage 信息
            if hasattr(chunk, 'usage') and chunk.usage:
                usage_dict = chunk.usage.model_dump() if hasattr(chunk.usage, 'model_dump') else dict(chunk.usage)
                # Handle reasoning tokens from details if present
                if 'completion_tokens_details' in usage_dict:
                    details = usage_dict['completion_tokens_details']
                    if 'reasoning_tokens' in details:
                        usage_dict['reasoning_tokens'] = details['reasoning_tokens']
                
                return ChatCompletionChunk(
                    type="usage",
                    content=None,
                    thinking=None,
                    tool_call=None,
                    usage=usage_dict,
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

        # OpenRouter 流式模式下不分离 reasoning，直接处理工具调用和内容

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

        # 提取推理内容
        reasoning_content = None
        reasoning_details = getattr(message, 'reasoning_details', None)
        if reasoning_details and isinstance(reasoning_details, list):
            # 从列表中提取所有 type='reasoning.text' 的 text 字段
            texts = []
            for item in reasoning_details:
                if isinstance(item, dict) and item.get('type') == 'reasoning.text':
                    text = item.get('text', '')
                    if text:
                        texts.append(text)
            reasoning_content = ''.join(texts) if texts else None
        
        # 或者使用 reasoning 字符串字段作为备选
        if not reasoning_content:
            reasoning_content = getattr(message, 'reasoning', None)

        usage_dict = response.usage.model_dump() if response.usage and hasattr(response.usage, 'model_dump') else (dict(response.usage) if response.usage else None)
        if usage_dict and 'completion_tokens_details' in usage_dict:
            details = usage_dict['completion_tokens_details']
            if 'reasoning_tokens' in details:
                usage_dict['reasoning_tokens'] = details['reasoning_tokens']

        result = ChatCompletionResponse(
            content=message.content,
            reasoning_content=reasoning_content,
            tool_calls=[tc.model_dump() for tc in message.tool_calls] if message.tool_calls else None,
            usage=usage_dict,
            model=response.model,
            finish_reason=response.choices[0].finish_reason,
        )

        # 处理图像生成结果
        images = getattr(message, 'images', None)
        if images:
            result["images"] = images

        return result

    def _handle_error(self, error: Exception) -> LLMException:
        """错误处理"""
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
            elif status_code == 403:
                return ModelUnavailableError(
                    model_id=self.model_id,
                    reason="Access denied"
                )
            elif status_code == 502:
                return ProviderConnectionError(
                    provider=self.PROVIDER,
                    endpoint=self.base_url
                )
            elif status_code == 503:
                return ModelUnavailableError(
                    model_id=self.model_id,
                    reason="Service unavailable"
                )
            elif status_code == 504:
                return ProviderTimeoutError(timeout_seconds=self.timeout)

        if isinstance(error, LLMException):
            return error

        return ProviderConnectionError(
            provider=self.PROVIDER,
            endpoint=self.base_url
        )

    def switch_model(self, model_id: str) -> None:
        """动态切换模型

        Args:
            model_id: 新的模型 ID
        """
        self.model_id = model_id

    async def list_models(self) -> list[ModelInfo]:
        """获取可用模型列表"""
        # 返回预定义的模型能力
        models = []
        for model_id, capabilities in self.MODEL_CAPABILITIES.items():
            models.append(ModelInfo(
                id=model_id,
                name=model_id.split("/")[-1],
                context_length=128000,  # 默认值
                supports_vision=capabilities.get("supports_vision", False),
                supports_tools=capabilities.get("supports_tools", False),
                supports_reasoning=capabilities.get("supports_reasoning", False),
                supports_audio=False,
            ))
        return models

    async def validate_credentials(self) -> bool:
        """验证凭证"""
        try:
            # 发送一个简单请求验证
            await self._client.models.list()
            return True
        except Exception:
            return False

    def supports_feature(self, feature: str) -> bool:
        """检查当前模型是否支持特定功能"""
        capabilities = self.MODEL_CAPABILITIES.get(self.model_id, {})
        feature_map = {
            "vision": capabilities.get("supports_vision", False),
            "tools": capabilities.get("supports_tools", False),
            "reasoning": capabilities.get("supports_reasoning", False),
            "image_generation": capabilities.get("supports_image_generation", False),
            "streaming": True,
        }
        return feature_map.get(feature, False)

    async def close(self) -> None:
        """关闭连接"""
        if self._client is not None:
            await self._client.close()
            self._client = None
