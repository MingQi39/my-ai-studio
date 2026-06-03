"""
Qwen (阿里云百炼) 官方直连适配器

特殊功能：
- 视觉理解 (qwen-vl 系列)
- 思考模式 (enable_thinking)
"""

from typing import AsyncIterator, Any

from .base import OpenAICompatibleAdapter
from ..types import ChatMessage, ChatCompletionChunk, ModelInfo, ChatCompletionResponse


class QwenAdapter(OpenAICompatibleAdapter):
    """Qwen (阿里云百炼) 官方直连适配器

    特殊功能：
    - 视觉理解：qwen-vl 系列模型
    - 思考模式：通过 enable_thinking 参数启用，thinking_budget 限制 token 数
    """

    PROVIDER = "qwen"
    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    SUPPORTED_MODELS: dict[str, ModelInfo] = {
        "qwen-plus": ModelInfo(
            id="qwen-plus",
            name="Qwen Plus",
            context_length=131072,
            supports_vision=False,
            supports_tools=True,
            supports_reasoning=False,
            supports_audio=False,
        ),
        "qwen3-plus": ModelInfo(
            id="qwen3-plus",
            name="Qwen3 Plus",
            context_length=131072,
            supports_vision=False,
            supports_tools=True,
            supports_reasoning=True,
            supports_audio=False,
        ),
        "qwen-vl-plus": ModelInfo(
            id="qwen-vl-plus",
            name="Qwen VL Plus",
            context_length=32768,
            supports_vision=True,
            supports_tools=True,
            supports_reasoning=False,
            supports_audio=False,
        ),
        "qwen-vl-max": ModelInfo(
            id="qwen-vl-max",
            name="Qwen VL Max",
            context_length=32768,
            supports_vision=True,
            supports_tools=True,
            supports_reasoning=False,
            supports_audio=False,
        ),
        "qwen3-vl-plus": ModelInfo(
            id="qwen3-vl-plus",
            name="Qwen3 VL Plus",
            context_length=32768,
            supports_vision=True,
            supports_tools=True,
            supports_reasoning=True,
            supports_audio=False,
        ),
    }

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model_id: str = "qwen-plus",
        timeout: int = 120,
        enable_thinking: bool = False,
        thinking_budget: int | None = None,
    ):
        """初始化 Qwen 适配器

        Args:
            api_key: Qwen API Key (阿里云百炼)
            base_url: API 基础 URL，默认为官方地址
            model_id: 模型 ID
            timeout: 请求超时时间（秒）
            enable_thinking: 是否启用思考模式
            thinking_budget: 思考 token 预算限制
        """
        super().__init__(api_key, base_url, model_id, timeout)
        self.enable_thinking = enable_thinking
        self.thinking_budget = thinking_budget

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
        """覆写：添加思考模式参数"""
        params = super()._build_request_params(
            messages, temperature, max_tokens, top_p, stream, tools, **kwargs
        )

        # 思考模式
        enable_thinking = kwargs.get("enable_thinking", self.enable_thinking)
        if enable_thinking:
            extra_body: dict[str, Any] = {"enable_thinking": True}
            thinking_budget = kwargs.get("thinking_budget", self.thinking_budget)
            if thinking_budget:
                extra_body["thinking_budget"] = thinking_budget
            params["extra_body"] = extra_body

        # 流式响应包含 usage
        if stream:
            params["stream_options"] = {"include_usage": True}

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

    def is_vision_model(self) -> bool:
        """检查当前模型是否为视觉模型"""
        model_info = self.SUPPORTED_MODELS.get(self.model_id)
        return model_info.get("supports_vision", False) if model_info else False
