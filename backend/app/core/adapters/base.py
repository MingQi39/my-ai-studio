"""
LLM 适配器抽象基类

定义所有适配器必须实现的接口。
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Any

from .types import ChatMessage, ChatCompletionChunk, ModelInfo, ChatCompletionResponse


class BaseLLMAdapter(ABC):
    """LLM 适配器抽象基类

    所有适配器必须继承此类并实现抽象方法。
    """

    PROVIDER: str = "base"
    DEFAULT_BASE_URL: str = ""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_id: str,
        timeout: int = 120
    ):
        """初始化适配器

        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            model_id: 模型 ID
            timeout: 请求超时时间（秒）
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model_id = model_id
        self.timeout = timeout
        self._client: Any = None

    @abstractmethod
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
        """执行聊天补全

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            top_p: Top-p 采样参数
            stream: 是否流式响应
            tools: 工具定义列表
            **kwargs: 其他参数

        Returns:
            流式响应时返回 AsyncIterator[ChatCompletionChunk]
            非流式响应时返回 ChatCompletionResponse
        """
        ...

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """列出可用模型

        Returns:
            模型信息列表
        """
        ...

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """验证凭证有效性

        Returns:
            凭证是否有效
        """
        ...

    @abstractmethod
    def supports_feature(self, feature: str) -> bool:
        """检查是否支持特定功能

        Args:
            feature: 功能名称 (vision, tools, reasoning, audio, streaming)

        Returns:
            是否支持
        """
        ...

    async def close(self) -> None:
        """关闭连接"""
        if self._client is not None:
            if hasattr(self._client, 'close'):
                await self._client.close()
            self._client = None

    async def __aenter__(self) -> "BaseLLMAdapter":
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口"""
        await self.close()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(provider={self.PROVIDER!r}, model={self.model_id!r})"
