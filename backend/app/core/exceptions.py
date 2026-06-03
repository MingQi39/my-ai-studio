"""
自定义异常层级

所有 LLM 相关的异常类定义，用于统一错误处理。
"""

from datetime import datetime


class LLMException(Exception):
    """LLM 异常基类"""

    def __init__(
        self,
        message: str,
        error_code: str,
        details: dict | None = None,
        status_code: int = 500
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.status_code = status_code
        self.timestamp = datetime.utcnow()
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "status_code": self.status_code,
            "timestamp": self.timestamp.isoformat(),
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(error_code={self.error_code!r}, message={self.message!r})"


class RateLimitError(LLMException):
    """速率限制错误 (429)"""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            message=f"Rate limit exceeded. Retry after {retry_after} seconds",
            error_code="RATE_LIMIT_EXCEEDED",
            details={"retry_after": retry_after},
            status_code=429
        )
        self.retry_after = retry_after


class TokenLimitError(LLMException):
    """Token 超限错误 (400)"""

    def __init__(self, max_tokens: int, requested_tokens: int):
        super().__init__(
            message=f"Token limit exceeded: {requested_tokens} > {max_tokens}",
            error_code="TOKEN_LIMIT_EXCEEDED",
            details={"max_tokens": max_tokens, "requested_tokens": requested_tokens},
            status_code=400
        )
        self.max_tokens = max_tokens
        self.requested_tokens = requested_tokens


class ModelUnavailableError(LLMException):
    """模型不可用错误 (503)"""

    def __init__(self, model_id: str, reason: str | None = None):
        super().__init__(
            message=f"Model unavailable: {model_id}",
            error_code="MODEL_UNAVAILABLE",
            details={"model_id": model_id, "reason": reason},
            status_code=503
        )
        self.model_id = model_id
        self.reason = reason


class AuthenticationError(LLMException):
    """认证失败错误 (401)"""

    def __init__(self, provider: str):
        super().__init__(
            message=f"Authentication failed for provider: {provider}",
            error_code="AUTH_FAILED",
            details={"provider": provider},
            status_code=401
        )
        self.provider = provider


class InsufficientBalanceError(LLMException):
    """余额不足错误 (402)"""

    def __init__(self, provider: str):
        super().__init__(
            message=f"Insufficient balance for provider: {provider}",
            error_code="INSUFFICIENT_BALANCE",
            details={"provider": provider},
            status_code=402
        )
        self.provider = provider


class ProviderConnectionError(LLMException):
    """连接失败错误 (502)"""

    def __init__(self, provider: str, endpoint: str):
        super().__init__(
            message=f"Connection failed to {provider}",
            error_code="CONNECTION_FAILED",
            details={"provider": provider, "endpoint": endpoint},
            status_code=502
        )
        self.provider = provider
        self.endpoint = endpoint


class ProviderTimeoutError(LLMException):
    """超时错误 (504)"""

    def __init__(self, timeout_seconds: int):
        super().__init__(
            message=f"Request timeout after {timeout_seconds} seconds",
            error_code="TIMEOUT",
            details={"timeout_seconds": timeout_seconds},
            status_code=504
        )
        self.timeout_seconds = timeout_seconds


class ConfigurationError(LLMException):
    """配置错误 (400)"""

    def __init__(self, config_key: str, reason: str):
        super().__init__(
            message=f"Configuration error for {config_key}: {reason}",
            error_code="CONFIG_INVALID",
            details={"config_key": config_key, "reason": reason},
            status_code=400
        )
        self.config_key = config_key
        self.reason = reason


class UnsupportedFeatureError(LLMException):
    """不支持的功能错误 (400)"""

    def __init__(self, feature: str, provider: str):
        super().__init__(
            message=f"Feature '{feature}' not supported by {provider}",
            error_code="UNSUPPORTED_FEATURE",
            details={"feature": feature, "provider": provider},
            status_code=400
        )
        self.feature = feature
        self.provider = provider


class ImageProcessingError(LLMException):
    """图像处理错误 (400)"""

    def __init__(self, reason: str, image_url: str | None = None):
        super().__init__(
            message=f"Image processing failed: {reason}",
            error_code="IMAGE_PROCESSING_FAILED",
            details={"reason": reason, "image_url": image_url},
            status_code=400
        )
        self.reason = reason
        self.image_url = image_url


class CircuitBreakerOpenError(LLMException):
    """熔断器打开错误 (503)"""

    def __init__(self, provider: str):
        super().__init__(
            message=f"Circuit breaker is open for provider: {provider}",
            error_code="CIRCUIT_BREAKER_OPEN",
            details={"provider": provider},
            status_code=503
        )
        self.provider = provider
