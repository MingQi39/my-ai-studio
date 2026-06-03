"""
官方直连适配器模块
"""

from .base import OpenAICompatibleAdapter
from .deepseek import DeepSeekAdapter
from .qwen import QwenAdapter

__all__ = [
    "OpenAICompatibleAdapter",
    "DeepSeekAdapter",
    "QwenAdapter",
]
