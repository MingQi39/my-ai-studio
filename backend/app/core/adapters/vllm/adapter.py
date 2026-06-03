"""
vLLM 适配器（占位）

高性能本地推理引擎适配器。
后续扩展实现。
"""

from typing import AsyncIterator

from ..base import BaseLLMAdapter
from ..types import ChatMessage, ChatCompletionChunk, ModelInfo, ChatCompletionResponse
from ...exceptions import UnsupportedFeatureError


class VLLMAdapter(BaseLLMAdapter):
    """vLLM 适配器（占位）

    高性能本地推理引擎，兼容 OpenAI API。
    后续扩展实现。
    """

    PROVIDER = "vllm"
    DEFAULT_BASE_URL = "http://localhost:8000/v1"

    def __init__(
        self,
        api_key: str = "",
        base_url: str | None = None,
        model_id: str = "",
        timeout: int = 300,
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url or self.DEFAULT_BASE_URL,
            model_id=model_id,
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
        """聊天补全（占位）"""
        raise UnsupportedFeatureError(
            feature="chat_completion",
            provider=self.PROVIDER
        )

    async def list_models(self) -> list[ModelInfo]:
        """列出可用模型（占位）"""
        return []

    async def validate_credentials(self) -> bool:
        """验证凭证（占位）"""
        return False

    def supports_feature(self, feature: str) -> bool:
        """检查功能支持（占位）"""
        return False
