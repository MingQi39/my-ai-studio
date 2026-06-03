"""
重试机制与熔断器

提供异步重试装饰器和熔断器实现。
"""

import asyncio
import random
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from functools import wraps
from typing import Callable, TypeVar, ParamSpec, Any

from .exceptions import (
    LLMException,
    RateLimitError,
    ProviderTimeoutError,
    ProviderConnectionError,
    CircuitBreakerOpenError,
)

P = ParamSpec('P')
T = TypeVar('T')


class RetryStrategy(Enum):
    """重试策略"""
    EXPONENTIAL = "exponential"  # 指数退避
    LINEAR = "linear"            # 线性退避
    CONSTANT = "constant"        # 固定间隔


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    jitter: bool = True  # ±10% 随机抖动
    retryable_exceptions: tuple = (
        RateLimitError,
        ProviderTimeoutError,
        ProviderConnectionError,
    )


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """计算重试延迟时间

    Args:
        attempt: 当前重试次数（从 0 开始）
        config: 重试配置

    Returns:
        延迟时间（秒）
    """
    if config.strategy == RetryStrategy.EXPONENTIAL:
        delay = config.base_delay * (2 ** attempt)
    elif config.strategy == RetryStrategy.LINEAR:
        delay = config.base_delay * (attempt + 1)
    else:  # CONSTANT
        delay = config.base_delay

    # 应用最大延迟限制
    delay = min(delay, config.max_delay)

    # 应用随机抖动 (±10%)
    if config.jitter:
        jitter_range = delay * 0.1
        delay += random.uniform(-jitter_range, jitter_range)

    return max(0, delay)


def async_retry(config: RetryConfig | None = None):
    """异步重试装饰器

    Args:
        config: 重试配置，默认使用 RetryConfig()

    Example:
        @async_retry(config=RetryConfig(max_retries=3))
        async def call_api():
            ...
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e
                    if attempt < config.max_retries:
                        delay = calculate_delay(attempt, config)
                        await asyncio.sleep(delay)
                    continue
                except Exception:
                    raise

            raise last_exception

        return wrapper
    return decorator


class CircuitBreakerState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常状态，允许请求
    OPEN = "open"          # 熔断状态，拒绝请求
    HALF_OPEN = "half_open"  # 半开状态，允许探测请求


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5       # 连续失败次数阈值
    recovery_timeout: int = 60       # 熔断恢复时间（秒）
    half_open_max_calls: int = 3     # 半开状态最大探测次数


class CircuitBreaker:
    """熔断器实现

    状态转换：
    - CLOSED -> OPEN: 连续失败次数达到阈值
    - OPEN -> HALF_OPEN: 恢复超时后
    - HALF_OPEN -> CLOSED: 探测成功次数达到阈值
    - HALF_OPEN -> OPEN: 探测失败
    """

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitBreakerState:
        """获取当前状态"""
        return self._state

    @property
    def failure_count(self) -> int:
        """获取失败计数"""
        return self._failure_count

    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """执行调用（带熔断保护）

        Args:
            func: 要执行的异步函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数返回值

        Raises:
            CircuitBreakerOpenError: 熔断器打开时
        """
        async with self._lock:
            if self._state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitBreakerState.HALF_OPEN
                    self._success_count = 0
                else:
                    raise CircuitBreakerOpenError(self.name)

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise

    async def _on_success(self) -> None:
        """成功回调"""
        async with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.half_open_max_calls:
                    self._state = CircuitBreakerState.CLOSED
                    self._failure_count = 0
            else:
                self._failure_count = 0

    async def _on_failure(self) -> None:
        """失败回调"""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.utcnow()

            if self._state == CircuitBreakerState.HALF_OPEN:
                self._state = CircuitBreakerState.OPEN
            elif self._failure_count >= self.config.failure_threshold:
                self._state = CircuitBreakerState.OPEN

    def _should_attempt_reset(self) -> bool:
        """判断是否应该尝试恢复"""
        if self._last_failure_time is None:
            return True
        elapsed = (datetime.utcnow() - self._last_failure_time).total_seconds()
        return elapsed >= self.config.recovery_timeout

    async def reset(self) -> None:
        """手动重置熔断器"""
        async with self._lock:
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None

    def get_state_info(self) -> dict:
        """获取状态信息"""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time.isoformat() if self._last_failure_time else None,
        }


class CircuitBreakerRegistry:
    """熔断器注册表（单例）

    按 provider 管理多个熔断器实例。
    """

    _instance: "CircuitBreakerRegistry | None" = None
    _breakers: dict[str, CircuitBreaker]

    def __new__(cls) -> "CircuitBreakerRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._breakers = {}
        return cls._instance

    def get_or_create(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None
    ) -> CircuitBreaker:
        """获取或创建熔断器

        Args:
            name: 熔断器名称（通常是 provider 名称）
            config: 熔断器配置

        Returns:
            熔断器实例
        """
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]

    def get(self, name: str) -> CircuitBreaker | None:
        """获取熔断器

        Args:
            name: 熔断器名称

        Returns:
            熔断器实例，不存在则返回 None
        """
        return self._breakers.get(name)

    def reset_all(self) -> None:
        """重置所有熔断器"""
        for breaker in self._breakers.values():
            asyncio.create_task(breaker.reset())

    def get_all_states(self) -> list[dict]:
        """获取所有熔断器状态"""
        return [breaker.get_state_info() for breaker in self._breakers.values()]


# 全局熔断器注册表
circuit_breaker_registry = CircuitBreakerRegistry()
