"""
适配器模块导出
"""

from .base import BaseLLMAdapter
from .types import (
    ContentBlock,
    ChatMessage,
    ChatCompletionChunk,
    ModelInfo,
    ChatCompletionResponse,
    ToolCall,
    UsageInfo,
)
from .factory import LLMAdapterFactory, adapter_factory
from .official import OpenAICompatibleAdapter, DeepSeekAdapter, QwenAdapter
from .openrouter import OpenRouterAdapter
from .ollama import OllamaAdapter
from .vllm import VLLMAdapter
from .omp import OmpAdapter

__all__ = [
    # 基类
    "BaseLLMAdapter",
    # 类型
    "ContentBlock",
    "ChatMessage",
    "ChatCompletionChunk",
    "ModelInfo",
    "ChatCompletionResponse",
    "ToolCall",
    "UsageInfo",
    # 工厂
    "LLMAdapterFactory",
    "adapter_factory",
    # 官方直连适配器
    "OpenAICompatibleAdapter",
    "DeepSeekAdapter",
    "QwenAdapter",
    # OpenRouter 适配器
    "OpenRouterAdapter",
    # 本地适配器
    "OllamaAdapter",
    "VLLMAdapter",
    "OmpAdapter",
]
