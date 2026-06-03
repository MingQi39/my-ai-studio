# Phase 3: 核心逻辑与适配器

> **目标**: 实现可独立运行的核心模块，不依赖 Web 框架或 Service 层。
> **预计工时**: 3-4 天
> **前置依赖**: Phase 2 完成

---

## 1. 阶段概述

本阶段聚焦于 `core/` 目录的实现，包括 LLM 多模型适配器、自定义异常层级、重试机制、熔断器和安全工具。这些模块必须能够独立测试，不依赖 FastAPI 或数据库。

---

## 2. 任务清单

### 2.1 自定义异常层级

- [ ] 创建 `backend/app/core/exceptions.py`

#### 2.1.1 基础异常类

- [ ] 定义 `LLMException` 基类
  ```python
  class LLMException(Exception):
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
  ```

#### 2.1.2 具体异常类

- [ ] 定义 `RateLimitError`
  - [ ] `retry_after`: int (秒)
  - [ ] `error_code`: "RATE_LIMIT_EXCEEDED"
  - [ ] `status_code`: 429

- [ ] 定义 `TokenLimitError`
  - [ ] `max_tokens`: int
  - [ ] `requested_tokens`: int
  - [ ] `error_code`: "TOKEN_LIMIT_EXCEEDED"
  - [ ] `status_code`: 400

- [ ] 定义 `ModelUnavailableError`
  - [ ] `model_id`: str
  - [ ] `reason`: str | None
  - [ ] `error_code`: "MODEL_UNAVAILABLE"
  - [ ] `status_code`: 503

- [ ] 定义 `AuthenticationError`
  - [ ] `provider`: str
  - [ ] `error_code`: "AUTH_FAILED"
  - [ ] `status_code`: 401

- [ ] 定义 `ProviderConnectionError`
  - [ ] `provider`: str
  - [ ] `endpoint`: str
  - [ ] `error_code`: "CONNECTION_FAILED"
  - [ ] `status_code`: 502

- [ ] 定义 `ProviderTimeoutError`
  - [ ] `timeout_seconds`: int
  - [ ] `error_code`: "TIMEOUT"
  - [ ] `status_code`: 504

- [ ] 定义 `ConfigurationError`
  - [ ] `config_key`: str
  - [ ] `reason`: str
  - [ ] `error_code`: "CONFIG_INVALID"
  - [ ] `status_code`: 400

- [ ] 定义 `BatchProcessingError`
  - [ ] `batch_id`: str
  - [ ] `failed_items`: int
  - [ ] `error_code`: "BATCH_FAILED"
  - [ ] `status_code`: 500

- [ ] 定义 `FileProcessingError`
  - [ ] `file_name`: str
  - [ ] `reason`: str
  - [ ] `error_code`: "FILE_PROCESSING_FAILED"
  - [ ] `status_code`: 400

- [ ] 定义 `UnsupportedFeatureError`
  - [ ] `feature`: str
  - [ ] `provider`: str
  - [ ] `error_code`: "UNSUPPORTED_FEATURE"
  - [ ] `status_code`: 400

### 2.2 重试机制与熔断器

- [ ] 创建 `backend/app/core/retry.py`

#### 2.2.1 重试策略

- [ ] 定义 `RetryStrategy` 枚举
  - [ ] `EXPONENTIAL`: 指数退避
  - [ ] `LINEAR`: 线性退避
  - [ ] `CONSTANT`: 固定间隔

- [ ] 定义 `RetryConfig` 配置类
  - [ ] `max_retries`: int = 3
  - [ ] `base_delay`: float = 1.0
  - [ ] `max_delay`: float = 60.0
  - [ ] `strategy`: RetryStrategy = EXPONENTIAL
  - [ ] `jitter`: bool = True (±10% 随机抖动)
  - [ ] `retryable_exceptions`: tuple = (RateLimitError, ProviderTimeoutError, ProviderConnectionError)

- [ ] 实现 `calculate_delay(attempt: int, config: RetryConfig) -> float`
  - [ ] 指数退避: `base_delay * (2 ** attempt)`
  - [ ] 线性退避: `base_delay * (attempt + 1)`
  - [ ] 固定间隔: `base_delay`
  - [ ] 应用最大延迟限制
  - [ ] 应用随机抖动

- [ ] 实现 `@retry` 装饰器 (同步版本)
  ```python
  @retry(config=RetryConfig())
  def call_api():
      ...
  ```

- [ ] 实现 `@async_retry` 装饰器 (异步版本)
  ```python
  @async_retry(config=RetryConfig())
  async def call_api():
      ...
  ```

#### 2.2.2 熔断器

- [ ] 定义 `CircuitBreakerState` 枚举
  - [ ] `CLOSED`: 正常状态，允许请求
  - [ ] `OPEN`: 熔断状态，拒绝请求
  - [ ] `HALF_OPEN`: 半开状态，允许探测请求

- [ ] 定义 `CircuitBreakerConfig` 配置类
  - [ ] `failure_threshold`: int = 5 (连续失败次数阈值)
  - [ ] `recovery_timeout`: int = 60 (熔断恢复时间，秒)
  - [ ] `half_open_max_calls`: int = 3 (半开状态最大探测次数)
  - [ ] `expected_exception`: type = LLMException

- [ ] 实现 `CircuitBreaker` 类
  - [ ] `state`: CircuitBreakerState
  - [ ] `failure_count`: int
  - [ ] `success_count`: int
  - [ ] `last_failure_time`: datetime | None
  - [ ] `call(func, *args, **kwargs)`: 同步调用
  - [ ] `call_async(func, *args, **kwargs)`: 异步调用
  - [ ] `_on_success()`: 成功回调
  - [ ] `_on_failure()`: 失败回调
  - [ ] `_should_attempt_reset()`: 判断是否尝试恢复
  - [ ] `reset()`: 手动重置
  - [ ] `get_state()`: 获取当前状态

- [ ] 实现 `CircuitBreakerRegistry` 单例
  - [ ] 按 provider 管理多个熔断器实例
  - [ ] `get_or_create(provider: str) -> CircuitBreaker`

### 2.3 安全工具

- [ ] 创建 `backend/app/core/security.py`

#### 2.3.1 API Key 加密

- [ ] 实现 `APIKeyEncryptor` 类
  - [ ] 使用 `cryptography.fernet.Fernet`
  - [ ] `__init__(encryption_key: str)`: 从配置读取密钥
  - [ ] `encrypt(plain_text: str) -> str`: 加密
  - [ ] `decrypt(cipher_text: str) -> str`: 解密
  - [ ] `generate_key() -> str`: 生成新密钥 (工具方法)

- [ ] 创建全局 `api_key_encryptor` 实例

#### 2.3.2 密钥验证

- [ ] 实现 `validate_api_key_format(api_key: str, provider: str) -> bool`
  - [ ] OpenAI: `sk-` 前缀
  - [ ] Anthropic: `sk-ant-` 前缀
  - [ ] DeepSeek: 无特定格式
  - [ ] 其他: 基本长度检查

### 2.4 LLM 适配器基类

- [ ] 创建 `backend/app/core/llm_adapter.py`

#### 2.4.1 类型定义

- [ ] 定义 `ChatMessage` TypedDict
  ```python
  class ChatMessage(TypedDict):
      role: Literal["system", "user", "assistant"]
      content: str | list[dict]  # 支持多模态
  ```

- [ ] 定义 `ChatCompletionChunk` TypedDict
  ```python
  class ChatCompletionChunk(TypedDict):
      type: Literal["content", "thinking", "tool_call", "usage", "done", "error"]
      content: str | None
      thinking: str | None
      tool_call: dict | None
      usage: dict | None
      error: str | None
  ```

- [ ] 定义 `ModelInfo` TypedDict
  ```python
  class ModelInfo(TypedDict):
      id: str
      name: str
      context_length: int
      supports_vision: bool
      supports_tools: bool
  ```

#### 2.4.2 基类定义

- [ ] 定义 `BaseLLMAdapter` 抽象基类
  ```python
  class BaseLLMAdapter(ABC):
      def __init__(
          self,
          api_key: str,
          base_url: str,
          model_id: str,
          timeout: int = 60
      ):
          ...

      @abstractmethod
      async def chat_completion(
          self,
          messages: list[ChatMessage],
          temperature: float = 0.7,
          max_tokens: int | None = None,
          top_p: float | None = None,
          stream: bool = True,
          tools: list[dict] | None = None,
      ) -> AsyncIterator[ChatCompletionChunk] | dict:
          """执行聊天补全"""
          ...

      @abstractmethod
      async def list_models(self) -> list[ModelInfo]:
          """列出可用模型"""
          ...

      @abstractmethod
      async def validate_credentials(self) -> bool:
          """验证凭证有效性"""
          ...

      @abstractmethod
      def supports_feature(self, feature: str) -> bool:
          """检查是否支持特定功能"""
          ...

      async def close(self):
          """关闭连接"""
          ...
  ```

### 2.5 OpenAI 兼容适配器

- [ ] 创建 `backend/app/core/adapters/openai_adapter.py`

- [ ] 实现 `OpenAIAdapter(BaseLLMAdapter)`
  - [ ] 使用 `httpx.AsyncClient` 或 `openai.AsyncOpenAI`
  - [ ] 支持流式响应
  - [ ] 支持多模态输入 (图片 base64)
  - [ ] 支持工具调用 (function calling)
  - [ ] 解析 reasoning tokens (如果模型支持)

- [ ] 实现 `chat_completion` 方法
  - [ ] 构建请求体
  - [ ] 处理流式响应 (SSE 解析)
  - [ ] 处理非流式响应
  - [ ] 错误映射到自定义异常

- [ ] 实现 `list_models` 方法
  - [ ] 调用 `/v1/models` 端点
  - [ ] 解析响应

- [ ] 实现 `validate_credentials` 方法
  - [ ] 尝试列出模型
  - [ ] 捕获认证错误

- [ ] 实现 `supports_feature` 方法
  - [ ] `vision`: 检查模型是否支持图片
  - [ ] `tools`: 检查模型是否支持工具调用
  - [ ] `streaming`: 始终返回 True

### 2.6 Anthropic 适配器

- [ ] 创建 `backend/app/core/adapters/anthropic_adapter.py`

- [ ] 实现 `AnthropicAdapter(BaseLLMAdapter)`
  - [ ] 使用 `anthropic.AsyncAnthropic`
  - [ ] 支持流式响应
  - [ ] 支持多模态输入
  - [ ] 支持工具调用
  - [ ] 解析 thinking 内容 (extended thinking)

- [ ] 实现消息格式转换
  - [ ] OpenAI 格式 → Anthropic 格式
  - [ ] 处理 system message 特殊性

- [ ] 实现 `chat_completion` 方法
  - [ ] 使用 `messages.stream()` 或 `messages.create()`
  - [ ] 解析 `content_block_delta` 事件
  - [ ] 解析 `thinking` 块

- [ ] 实现 `list_models` 方法
  - [ ] 返回硬编码的 Claude 模型列表
  - [ ] (Anthropic API 不提供模型列表端点)

- [ ] 实现 `validate_credentials` 方法
  - [ ] 发送最小请求验证

### 2.7 Ollama 适配器

- [ ] 创建 `backend/app/core/adapters/ollama_adapter.py`

- [ ] 实现 `OllamaAdapter(BaseLLMAdapter)`
  - [ ] 使用 `httpx.AsyncClient`
  - [ ] 支持流式响应
  - [ ] 支持多模态 (LLaVA 等)
  - [ ] 本地模型无需 API Key

- [ ] 实现 `chat_completion` 方法
  - [ ] 调用 `/api/chat` 端点
  - [ ] 处理 NDJSON 流式响应

- [ ] 实现 `list_models` 方法
  - [ ] 调用 `/api/tags` 端点
  - [ ] 解析本地模型列表

- [ ] 实现 `validate_credentials` 方法
  - [ ] 检查 Ollama 服务是否运行
  - [ ] 调用 `/api/tags` 验证连接

### 2.8 适配器工厂

- [ ] 创建 `backend/app/core/adapters/__init__.py`

- [ ] 实现 `LLMAdapterFactory` 类
  ```python
  class LLMAdapterFactory:
      _adapters: dict[LLMProvider, type[BaseLLMAdapter]] = {
          LLMProvider.openai: OpenAIAdapter,
          LLMProvider.anthropic: AnthropicAdapter,
          LLMProvider.deepseek: OpenAIAdapter,
          LLMProvider.gemini: OpenAIAdapter,
          LLMProvider.qwen: OpenAIAdapter,
          LLMProvider.openrouter: OpenAIAdapter,
          LLMProvider.ollama: OllamaAdapter,
          LLMProvider.local: OpenAIAdapter,
      }

      _default_base_urls: dict[LLMProvider, str] = {
          LLMProvider.openai: "https://api.openai.com/v1",
          LLMProvider.anthropic: "https://api.anthropic.com",
          LLMProvider.deepseek: "https://api.deepseek.com/v1",
          LLMProvider.gemini: "https://generativelanguage.googleapis.com/v1beta/openai",
          LLMProvider.qwen: "https://dashscope.aliyuncs.com/compatible-mode/v1",
          LLMProvider.openrouter: "https://openrouter.ai/api/v1",
          LLMProvider.ollama: "http://localhost:11434",
      }

      @classmethod
      def create(
          cls,
          provider: LLMProvider,
          api_key: str,
          base_url: str | None = None,
          model_id: str,
          **kwargs
      ) -> BaseLLMAdapter:
          ...
  ```

- [ ] 导出所有适配器和工厂

### 2.9 流式响应工具

- [ ] 创建 `backend/app/core/streaming.py`

- [ ] 实现 `SSEFormatter` 类
  - [ ] `format_chunk(data: dict) -> str`: 格式化为 SSE 格式
  - [ ] `format_error(error: LLMException) -> str`: 格式化错误
  - [ ] `format_done(usage: dict | None) -> str`: 格式化完成信号

- [ ] 实现 `StreamBuffer` 类
  - [ ] 缓冲流式内容
  - [ ] 支持内容聚合
  - [ ] 支持 thinking 内容分离

### 2.10 模块导出

- [ ] 更新 `backend/app/core/__init__.py`
  - [ ] 导出所有异常类
  - [ ] 导出重试装饰器和熔断器
  - [ ] 导出安全工具
  - [ ] 导出适配器工厂

---

## 3. 验收标准

### 3.1 功能验收

- [ ] 异常类可正确实例化和序列化
- [ ] 重试装饰器在指定异常时正确重试
- [ ] 熔断器在达到阈值时正确熔断
- [ ] API Key 加密/解密正确
- [ ] OpenAI 适配器可连接 OpenAI API (需真实 Key)
- [ ] OpenAI 适配器可连接 DeepSeek API
- [ ] Anthropic 适配器可连接 Claude API (需真实 Key)
- [ ] Ollama 适配器可连接本地 Ollama (需运行 Ollama)
- [ ] 流式响应正确解析

### 3.2 独立性验收

- [ ] 所有 core 模块可独立导入
- [ ] 不依赖 FastAPI
- [ ] 不依赖 SQLAlchemy
- [ ] 不依赖 Service 层

### 3.3 测试验收

- [ ] 创建 `backend/tests/test_exceptions.py`
- [ ] 创建 `backend/tests/test_retry.py`
- [ ] 创建 `backend/tests/test_circuit_breaker.py`
- [ ] 创建 `backend/tests/test_security.py`
- [ ] 创建 `backend/tests/test_adapters.py` (使用 Mock)
- [ ] 所有测试通过
- [ ] 测试覆盖率 > 80%

---

## 4. 目录结构预览

完成本阶段后，`core/` 目录结构应如下：

```
backend/app/core/
├── __init__.py
├── exceptions.py          # 自定义异常层级
├── retry.py               # 重试机制 + 熔断器
├── security.py            # API Key 加密
├── streaming.py           # SSE 流式工具
└── adapters/
    ├── __init__.py        # 适配器工厂
    ├── base.py            # 基类定义
    ├── openai_adapter.py  # OpenAI 兼容适配器
    ├── anthropic_adapter.py # Anthropic 适配器
    └── ollama_adapter.py  # Ollama 适配器
```

---

## 5. 注意事项

1. **必须独立可测试** - 不依赖 Web 框架
2. **异步优先** - 所有 I/O 操作使用 async/await
3. **错误映射要完整** - 将 SDK 异常映射到自定义异常
4. **流式响应要健壮** - 处理连接中断、超时等情况
5. **熔断器要线程安全** - 使用 asyncio.Lock
6. **API Key 不要日志输出** - 安全考虑
7. **超时配置要合理** - LLM 响应可能较慢

---

## 6. 下一阶段预告

完成本阶段后，进入 **Phase 4: 业务服务层**，将实现：
- ChatService: 聊天业务逻辑
- SessionService: 会话管理
- ModelService: 模型配置管理
- FileService: 文件上传处理
