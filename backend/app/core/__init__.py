"""
Core 模块

包含 LLM 适配器、异常、重试机制、配置管理和流式响应工具。
"""

# 异常类
from .exceptions import (
    LLMException,
    RateLimitError,
    TokenLimitError,
    ModelUnavailableError,
    AuthenticationError,
    InsufficientBalanceError,
    ProviderConnectionError,
    ProviderTimeoutError,
    ConfigurationError,
    UnsupportedFeatureError,
    ImageProcessingError,
    CircuitBreakerOpenError,
)

# 重试机制与熔断器
from .retry import (
    RetryStrategy,
    RetryConfig,
    calculate_delay,
    async_retry,
    CircuitBreakerState,
    CircuitBreakerConfig,
    CircuitBreaker,
    CircuitBreakerRegistry,
    circuit_breaker_registry,
)

# 配置管理
from .config import (
    AdapterType,
    OfficialProvider,
    Modality,
    ModelInfo,
    ProviderConfig,
    OpenRouterConfig,
    ConfigLoader,
    get_config_loader,
)

# 流式响应工具
from .stream_state import (
    StreamState,
    StreamStateManager,
    stream_state_manager,
)

from .streaming import (
    SSEFormatter,
    StreamBuffer,
)

# 适配器
from .adapters import (
    BaseLLMAdapter,
    ContentBlock,
    ChatMessage,
    ChatCompletionChunk,
    ChatCompletionResponse,
    ToolCall,
    UsageInfo,
    LLMAdapterFactory,
    adapter_factory,
    OpenAICompatibleAdapter,
    DeepSeekAdapter,
    QwenAdapter,
    OpenRouterAdapter,
    OllamaAdapter,
    VLLMAdapter,
)

__all__ = [
    # 异常类
    "LLMException",
    "RateLimitError",
    "TokenLimitError",
    "ModelUnavailableError",
    "AuthenticationError",
    "InsufficientBalanceError",
    "ProviderConnectionError",
    "ProviderTimeoutError",
    "ConfigurationError",
    "UnsupportedFeatureError",
    "ImageProcessingError",
    "CircuitBreakerOpenError",
    # 重试机制
    "RetryStrategy",
    "RetryConfig",
    "calculate_delay",
    "async_retry",
    # 熔断器
    "CircuitBreakerState",
    "CircuitBreakerConfig",
    "CircuitBreaker",
    "CircuitBreakerRegistry",
    "circuit_breaker_registry",
    # 配置
    "AdapterType",
    "OfficialProvider",
    "Modality",
    "ModelInfo",
    "ProviderConfig",
    "OpenRouterConfig",
    "ConfigLoader",
    "get_config_loader",
    # 流式响应
    "SSEFormatter",
    "StreamBuffer",
    # 适配器类型
    "BaseLLMAdapter",
    "ContentBlock",
    "ChatMessage",
    "ChatCompletionChunk",
    "ChatCompletionResponse",
    "ToolCall",
    "UsageInfo",
    # 适配器工厂
    "LLMAdapterFactory",
    "adapter_factory",
    # 适配器实现
    "OpenAICompatibleAdapter",
    "DeepSeekAdapter",
    "QwenAdapter",
    "OpenRouterAdapter",
    "OllamaAdapter",
    "VLLMAdapter",
]
