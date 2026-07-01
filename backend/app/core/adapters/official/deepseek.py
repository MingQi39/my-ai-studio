"""
DeepSeek 官方直连适配器

特殊功能：
- 思考模式 (reasoning_content)
- 支持 deepseek-chat 和 deepseek-reasoner 模型
"""

from typing import AsyncIterator, Any

from .base import OpenAICompatibleAdapter
from ..types import ChatMessage, ChatCompletionChunk, ModelInfo, ChatCompletionResponse


class DeepSeekAdapter(OpenAICompatibleAdapter):
    """DeepSeek 官方直连适配器

    特殊功能：
    - 思考模式：通过 reasoning_content 字段返回
    - 启用方式：使用 deepseek-reasoner 模型，或设置 enable_reasoning=True
    """

    PROVIDER = "deepseek"
    DEFAULT_BASE_URL = "https://api.deepseek.com"

    SUPPORTED_MODELS: dict[str, ModelInfo] = {
        "deepseek-chat": ModelInfo(
            id="deepseek-chat",
            name="DeepSeek Chat",
            context_length=64000,
            supports_vision=False,
            supports_tools=True,
            supports_reasoning=True,
            supports_audio=False,
        ),
        "deepseek-reasoner": ModelInfo(
            id="deepseek-reasoner",
            name="DeepSeek Reasoner",
            context_length=64000,
            supports_vision=False,
            supports_tools=True,
            supports_reasoning=True,
            supports_audio=False,
        ),
    }

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model_id: str = "deepseek-chat",
        timeout: int = 120,
        enable_reasoning: bool = True,  # 默认启用思考模式
    ):
        """初始化 DeepSeek 适配器

        Args:
            api_key: DeepSeek API Key
            base_url: API 基础 URL，默认为官方地址
            model_id: 模型 ID
            timeout: 请求超时时间（秒）
            enable_reasoning: 是否启用思考模式（对 deepseek-chat 有效，默认开启）
        """
        super().__init__(api_key, base_url, model_id, timeout)
        self.enable_reasoning = enable_reasoning

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
        """覆写：思考模式与 Function Calling 不能同时开启；json_schema 不可用"""
        params = super()._build_request_params(
            messages, temperature, max_tokens, top_p, stream, tools, **kwargs
        )

        # DeepSeek 不支持 tools 与 response_format 同传，且仅支持 json_object
        if tools:
            params.pop("response_format", None)
        elif params.get("response_format", {}).get("type") == "json_schema":
            params["response_format"] = {"type": "json_object"}

        if tools:
            params["tool_choice"] = "auto"
            return params

        enable_reasoning = kwargs.get("enable_reasoning", self.enable_reasoning)
        if enable_reasoning and self.model_id != "deepseek-reasoner":
            params["extra_body"] = {"thinking": {"type": "enabled"}}

        return params

    def _parse_chunk(self, chunk: Any) -> ChatCompletionChunk | None:
        """覆写：处理 reasoning_content 字段"""
        if not chunk.choices:
            return super()._parse_chunk(chunk)

        choice = chunk.choices[0]
        delta = choice.delta

        # 检查思维链内容
        reasoning_content = getattr(delta, 'reasoning_content', None)
        if reasoning_content:
            return ChatCompletionChunk(
                type="thinking",
                content=None,
                thinking=reasoning_content,
                tool_call=None,
                usage=None,
                error=None,
            )

        return super()._parse_chunk(chunk)

    def _handle_response(self, response: Any) -> ChatCompletionResponse:
        """覆写：处理非流式响应中的 reasoning_content"""
        result = super()._handle_response(response)
        message = response.choices[0].message
        result["reasoning_content"] = getattr(message, 'reasoning_content', None)
        return result
