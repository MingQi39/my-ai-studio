# Phase 3: 核心逻辑与适配器

---

## 1. 阶段概述

本阶段聚焦于 `core/` 目录的实现，包括 LLM 多模型适配器、自定义异常层级、重试机制、熔断器和配置管理。这些模块必须能够独立测试，不依赖 FastAPI 或数据库。

### 1.1 适配器架构总览

| 类型 | 描述 | 组织方式 | 状态 |
|------|------|----------|------|
| **官方直连** | 直接调用各厂商 API（DeepSeek、Qwen 等） | 按供应商划分 | ✅ 实现 |
| **OpenRouter** | 通过 OpenRouter 统一网关访问多模型 | 按模态划分 | ✅ 实现 |
| **Ollama** | 本地部署的开源模型 | - | 🔲 占位 |
| **vLLM** | 高性能本地推理引擎 | - | 🔲 占位 |

### 1.2 架构图

BaseLLMAdapter (抽象基类)
│
├── 第一类：官方直连适配器 (按供应商划分)
│   │
│   └── OpenAICompatibleAdapter (OpenAI 兼容基类)
│           ├── DeepSeekAdapter     → 特殊: reasoning_content
│           ├── QwenAdapter         → 特殊: enable_thinking, 视觉
│           ├── OpenAIAdapter       → 预留
│
├── 第二类：OpenRouter 适配器 (按模态划分)
│   │
│   └── OpenRouterAdapter
│           ├── 文本处理 (text)
│           ├── 图像处理 (vision)
│           └── 音频处理 (audio) → 预留
│
├── 第三类：Ollama 适配器 → 占位
│
└── 第四类：vLLM 适配器 → 占位


---

## 2. 任务清单

### 2.1 自定义异常层级

- [ ] 创建 `backend/app/core/exceptions.py`

#### 2.1.1 基础异常类

| 类名 | 描述 |
|------|------|
| `LLMException` | 基类，包含 message, error_code, details, status_code, timestamp |

#### 2.1.2 具体异常类

| 异常类 | error_code | status_code | 特殊字段 |
|--------|------------|-------------|----------|
| `RateLimitError` | RATE_LIMIT_EXCEEDED | 429 | retry_after: int |
| `TokenLimitError` | TOKEN_LIMIT_EXCEEDED | 400 | max_tokens, requested_tokens |
| `ModelUnavailableError` | MODEL_UNAVAILABLE | 503 | model_id, reason |
| `AuthenticationError` | AUTH_FAILED | 401 | provider |
| `InsufficientBalanceError` | INSUFFICIENT_BALANCE | 402 | provider |
| `ProviderConnectionError` | CONNECTION_FAILED | 502 | provider, endpoint |
| `ProviderTimeoutError` | TIMEOUT | 504 | timeout_seconds |
| `ConfigurationError` | CONFIG_INVALID | 400 | config_key, reason |
| `UnsupportedFeatureError` | UNSUPPORTED_FEATURE | 400 | feature, provider |
| `ImageProcessingError` | IMAGE_PROCESSING_FAILED | 400 | reason, image_url |
| `CircuitBreakerOpenError` | CIRCUIT_BREAKER_OPEN | 503 | provider |



### 2.2 重试机制与熔断器

- [ ] 创建 `backend/app/core/retry.py`

#### 2.2.1 重试策略

| 策略 | 描述 | 计算公式 |
|------|------|----------|
| `EXPONENTIAL` | 指数退避 | `base_delay * (2 ** attempt)` |
| `LINEAR` | 线性退避 | `base_delay * (attempt + 1)` |
| `CONSTANT` | 固定间隔 | `base_delay` |

#### 2.2.2 RetryConfig 配置项

| 配置项 | 类型 | 默认值 | 描述 |
|--------|------|--------|------|
| `max_retries` | int | 3 | 最大重试次数 |
| `base_delay` | float | 1.0 | 基础延迟（秒） |
| `max_delay` | float | 60.0 | 最大延迟（秒） |
| `strategy` | RetryStrategy | EXPONENTIAL | 重试策略 |
| `jitter` | bool | True | 是否添加 ±10% 随机抖动 |
| `retryable_exceptions` | tuple | (RateLimitError, ProviderTimeoutError, ProviderConnectionError) | 可重试的异常类型 |

#### 2.2.3 熔断器状态

| 状态 | 描述 |
|------|------|
| `CLOSED` | 正常状态，允许请求 |
| `OPEN` | 熔断状态，拒绝请求 |
| `HALF_OPEN` | 半开状态，允许探测请求 |

#### 2.2.4 CircuitBreakerConfig 配置项

| 配置项 | 类型 | 默认值 | 描述 |
|--------|------|--------|------|
| `failure_threshold` | int | 5 | 连续失败次数阈值 |
| `recovery_timeout` | int | 60 | 熔断恢复时间（秒） |
| `half_open_max_calls` | int | 3 | 半开状态最大探测次数 |

#### 2.2.5 需实现的组件

- [ ] `calculate_delay(attempt, config)` - 计算重试延迟
- [ ] `@async_retry` 装饰器 - 异步重试
- [ ] `CircuitBreaker` 类 - 熔断器（线程安全，使用 asyncio.Lock）
- [ ] `CircuitBreakerRegistry` 单例 - 按 provider 管理熔断器

---

### 2.3 配置管理

- [ ] 创建 `backend/app/core/config.py`
- [ ] 创建 `backend/config/providers.yaml`
- [ ] 创建 `backend/.env.example`

#### 2.3.1 枚举定义

| 枚举 | 值 |
|------|-----|
| `AdapterType` | OFFICIAL, OPENROUTER, OLLAMA, VLLM |
| `OfficialProvider` | DEEPSEEK, QWEN, OPENAI, ANTHROPIC, GEMINI |
| `Modality` | TEXT, VISION, AUDIO, MULTIMODAL |

#### 2.3.2 配置文件结构 (providers.yaml)

```yaml
# 第一类：官方直连（按供应商）
official:
  deepseek:
    base_url: "https://api.deepseek.com"
    api_key_env: "DEEPSEEK_API_KEY"  # 从环境变量读取
    timeout: 120
    models: [...]
  qwen:
    base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key_env: "QWEN_API_KEY"
    timeout: 120
    models: [...]

# 第二类：OpenRouter（按模态）
openrouter:
  base_url: "https://openrouter.ai/api/v1"
  api_key_env: "OPENROUTER_API_KEY"
  text_models: [...]
  vision_models: [...]
  audio_models: []  # 预留

# 第三类：Ollama（占位）
ollama:
  base_url: "http://localhost:11434"
  models: []

# 第四类：vLLM（占位）
vllm:
  base_url: "http://localhost:8000/v1"
  models: []

#### 2.3.3 ModelInfo 字段

| 字段 | 类型 | 描述 |
|------|------|------|
| id | str | 模型 ID |
| name | str | 显示名称 |
| context_length | int | 上下文长度 |
| supports_vision | bool | 是否支持视觉 |
| supports_tools | bool | 是否支持工具调用 |
| supports_reasoning | bool | 是否支持思考模式 |
| supports_audio | bool | 是否支持音频 |
| modality | Modality | 模态类型 |

#### 2.3.4 ConfigLoader 方法

| 方法 | 描述 |
|------|------|
| load() | 加载配置文件 |
| get_official_provider_config(provider) | 获取官方直连配置 |
| get_openrouter_config() | 获取 OpenRouter 配置 |
| get_ollama_config() | 获取 Ollama 配置 |
| get_vllm_config() | 获取 vLLM 配置 |
| get_api_key(env_var) | 从环境变量获取 API Key（必需） |
| get_api_key_optional(env_var) | 从环境变量获取 API Key（可选） |


#### 2.3.5 环境变量

| 变量名 | 描述 |
|------|------|
| DEEPSEEK_API_KEY | DeepSeek API Key |
| QWEN_API_KEY | Qwen (阿里云百炼) API Key |
| OPENAI_API_KEY | OpenAI API Key |
| ANTHROPIC_API_KEY | Anthropic API Key |
| GEMINI_API_KEY | Google Gemini API Key |
| OPENROUTER_API_KEY | OpenRouter API Key |


### 2.4 适配器基类

- [ ] 创建 `backend/app/core/adapters/base.py`
- [ ] 创建 `backend/app/core/adapters/types.py`

#### 2.4.1 类型定义

ContentBlock - 内容块（支持多模态）

| 字段 | 类型 | 描述 |
|------|------|------|
| type | Literal["text", "image_url", "image_base64", "audio"] | 内容类型 |
| text | str | None | 文本内容 |
| image_url | str | None | 图片 URL |
| image_base64 | str | None | Base64 编码图片 |
| mime_type | str | None | MIME 类型 |

ChatMessage - 聊天消息

| 字段 | 类型 | 描述 |
|------|------|------|
| role | Literal["system", "user", "assistant", "tool"] | 角色 |
| content | str | list[ContentBlock] | 内容（支持多模态） |
| tool_call_id | str | None | 工具调用 ID |
| tool_calls | list[dict] | None | 工具调用列表 |


ChatCompletionChunk - 流式响应块

| 字段 | 类型 | 描述 |
|------|------|------|
| type | Literal["content", "thinking", "tool_call", "usage", "done", "error"] | 块类型 |
| content | str | None | 文本内容 |
| thinking | str | None | 思考内容 |
| tool_call | dict | None | 工具调用 |
| usage | dict | None | Token 使用统计 |
| error | str | None | 错误信息 |


#### 2.4.2 BaseLLMAdapter 抽象基类

| 方法 | 描述 |
|------|------|
| __init__(api_key, base_url, model_id, timeout) | 初始化 |
| chat_completion(messages, temperature, max_tokens, top_p, stream, tools, **kwargs) | 聊天补全（抽象） |
| list_models() | 列出可用模型（抽象） |
| validate_credentials() | 验证凭证（抽象） |
| supports_feature(feature) | 检查功能支持（抽象） |
| close() | 关闭连接 |


## 2.5 第一类：官方直连适配器

- [ ] 创建 `backend/app/core/adapters/official/__init__.py`
- [ ] 创建 `backend/app/core/adapters/official/base.py` - OpenAICompatibleAdapter
- [ ] 创建 `backend/app/core/adapters/official/deepseek.py` - DeepSeekAdapter
- [ ] 创建 `backend/app/core/adapters/official/qwen.py` - QwenAdapter


### 2.5.1 OpenAICompatibleAdapter 基类

继承 BaseLLMAdapter，实现 OpenAI 兼容 API 的通用逻辑。

| 方法 | 描述 | 子类可覆写 |
|------|------|------|
| _build_request_params(...) | 构建请求参数 | ✅ |
| _convert_messages(messages) | 转换消息格式 | ✅ |
| _handle_stream_response(response) | 处理流式响应 | ✅ |
| _parse_chunk(chunk) | 解析响应块 | ✅ |
| _handle_response(response) | 处理非流式响应 | ✅ |
| _handle_error(error) | 错误处理 | ✅ |


### 2.5.2 DeepSeekAdapter

|属性	值
|------|------|
| PROVIDER | "deepseek" |
| DEFAULT_BASE_URL | "https://api.deepseek.com" |

特殊功能：

- [ ] 思考模式：通过 reasoning_content 字段返回
- [ ] 启用方式：使用 deepseek-reasoner 模型，或设置 extra_body={"thinking": {"type": "enabled"}}

支持的模型：

| 模型 ID | 视觉 | 工具 | 思考 |
|------|------|------|------|
| deepseek-chat | ❌ | ✅ | ✅ |
| deepseek-reasoner | ❌ | ✅ | ✅ |

覆写方法：

- [ ] _build_request_params: 添加思考模式参数
- [ ] _parse_chunk: 处理 reasoning_content 字段


### 2.5.3 QwenAdapter

| 属性 | 值 |
|------|------|
| PROVIDER | "qwen" |
| DEFAULT_BASE_URL | "https://dashscope.aliyuncs.com/compatible-mode/v1" |

特殊功能：

- [ ] 视觉理解：qwen-vl 系列模型
- [ ] 思考模式：通过 enable_thinking 参数启用，thinking_budget 限制 token 数

支持的模型：

| 模型 ID | 视觉 | 工具 | 思考 |
|------|------|------|------|
| qwen-plus | ❌ | ✅ | ❌ |
| qwen3-plus | ❌ | ✅ | ✅ |
| qwen-vl-plus | ✅ | ✅ | ❌ |
| qwen-vl-max | ✅ | ✅ | ❌ |
| qwen3-vl-plus | ✅ | ✅ | ✅ |

覆写方法：

- [ ] _build_request_params: 添加 enable_thinking, thinking_budget, stream_options
- [ ] _parse_chunk: 处理 reasoning_content 字段


## 2.6 第二类：OpenRouter 适配器
按模态组织，统一 API Key 和 Base URL，通过模型名称区分。

- [ ] 创建 `backend/app/core/adapters/openrouter/__init__.py`
- [ ] 创建 `backend/app/core/adapters/openrouter/adapter.py` - OpenRouterAdapter

### 2.6.1 OpenRouterAdapter

| 属性 | 值 |
|------|------|
| PROVIDER | "openrouter" |
| DEFAULT_BASE_URL | "https://openrouter.ai/api/v1" |

特殊功能：

- [ ] 推理模式：通过 extra_body={"reasoning": {"enabled": True}} 启用
- [ ] 多轮推理：需保留 reasoning_details 传回
- [ ] 图像生成：通过 extra_body={"modalities": ["image", "text"]} 启用
- [ ] 动态模型切换：switch_model(model_id) 方法

模态分类：

| 模态 | 配置键 | 示例模型 |
|------|------|------|
| 文本 | text_models | google/gemini-2.0-flash-001, anthropic/claude-3.5-sonnet |
| 视觉 | vision_models | google/gemini-2.5-pro-preview, openai/gpt-4o |
| 音频 | audio_models | 预留 |

覆写方法：

- [ ] _build_request_params: 添加 reasoning, modalities 参数
- [ ] _parse_chunk: 处理 reasoning_content 或 reasoning 字段
- [ ] _handle_response: 处理 reasoning_details, images 字段


##2.7 第三类：Ollama 适配器（占位）
- [ ] 创建 `backend/app/core/adapters/ollama/__init__.py`
- [ ] 创建 `backend/app/core/adapters/ollama/adapter.py` - OllamaAdapter

| 属性 | 值 |
|------|------|
| PROVIDER | "ollama" |
| DEFAULT_BASE_URL | "http://localhost:11434" |

说明： 本地部署，通常不需要 API Key。后续扩展实现。



## 2.8 第四类：vLLM 适配器（占位）
- [ ] 创建 `backend/app/core/adapters/vllm/__init__.py`
- [ ] 创建 `backend/app/core/adapters/vllm/adapter.py` - VLLMAdapter

| 属性 | 值 |
|------|------|
| PROVIDER | "vllm" |
| DEFAULT_BASE_URL | "http://localhost:8000/v1" |

说明： 高性能本地推理引擎，兼容 OpenAI API。后续扩展实现。


## 2.9 适配器工厂
- [ ] 创建 `backend/app/core/adapters/factory.py`

LLMAdapterFactory

| 方法 | 描述 |
|------|------|
| create_official(provider, model_id, **kwargs) | 创建官方直连适配器 |
| create_openrouter(model_id, **kwargs) | 创建 OpenRouter 适配器 |
| create_ollama(model_id, **kwargs) | 创建 Ollama 适配器 |
| create_vllm(model_id, **kwargs) | 创建 vLLM 适配器 |
| create(adapter_type, provider, model_id, **kwargs) | 通用创建方法 |


## 2.10 流式响应工具
- [ ] 创建 `backend/app/core/streaming.py`

### 2.10.1 SSEFormatter

| 方法 | 描述 |
|------|------|
| format_chunk(chunk: ChatCompletionChunk) | 格式化为 SSE 格式 |
| format_error(error: LLMException) | 格式化错误 |
| format_done(usage: dict | None) | 格式化完成信号 |


### 2.10.2 StreamBuffer

| 方法 | 描述 |
|------|------|
| append(chunk) | 添加内容块 |
| get_content() | 获取聚合的文本内容 |
| get_thinking() | 获取聚合的思考内容 |
| get_tool_calls() | 获取工具调用列表 |
| get_usage() | 获取 Token 使用统计 |

## 2.11 模块导出
- [ ] 更新 `backend/app/core/__init__.py`

导出内容：

- [ ] 所有异常类
- [ ] 重试装饰器和熔断器
- [ ] 配置加载器
- [ ] 适配器工厂
- [ ] 流式响应工具

# 3.目录结构
backend/
├── config/
│   └── providers.yaml          # Provider 配置文件
├── .env.example                # 环境变量示例
└── app/
    └── core/
        ├── __init__.py         # 模块导出
        ├── exceptions.py       # 自定义异常
        ├── retry.py            # 重试机制 + 熔断器
        ├── config.py           # 配置加载器
        ├── streaming.py        # 流式响应工具
        └── adapters/
            ├── __init__.py     # 适配器导出
            ├── base.py         # BaseLLMAdapter 抽象基类
            ├── types.py        # 类型定义
            ├── factory.py      # 适配器工厂
            ├── official/       # 第一类：官方直连
            │   ├── __init__.py
            │   ├── base.py     # OpenAICompatibleAdapter
            │   ├── deepseek.py # DeepSeekAdapter
            │   └── qwen.py     # QwenAdapter
            ├── openrouter/     # 第二类：OpenRouter
            │   ├── __init__.py
            │   └── adapter.py  # OpenRouterAdapter
            ├── ollama/         # 第三类：Ollama（占位）
            │   ├── __init__.py
            │   └── adapter.py  # OllamaAdapter
            └── vllm/           # 第四类：vLLM（占位）
                ├── __init__.py
                └── adapter.py  # VLLMAdapter


# 4. 验收标准
## 4.1 功能验收
- [] 异常类可正确实例化和序列化为 dict
- [ ] 重试装饰器在指定异常时正确重试
- [ ] 熔断器在达到阈值时正确熔断
- [ ] 配置加载器正确读取 YAML 和环境变量
- [ ] DeepSeekAdapter 可连接 DeepSeek API，正确处理 reasoning_content
- [ ] QwenAdapter 可连接阿里云百炼 API，正确处理视觉和思考模式
- [ ] OpenRouterAdapter 可连接 OpenRouter，正确处理多模型切换
- [ ] 流式响应正确解析各类 chunk

## 4.2 独立性验收
- [ ] 所有 core 模块可独立导入
- [ ] 不依赖 FastAPI
- [ ] 不依赖 SQLAlchemy
- [ ] 不依赖 Service 层
- [ ] API Key 不硬编码，通过环境变量管理

## 4.3 测试验收
- [ ] 创建 `backend/tests/core/test_exceptions.py`
- [ ] 创建 `backend/tests/core/test_retry.py`
- [ ] 创建 `backend/tests/core/test_circuit_breaker.py`
- [ ] 创建 `backend/tests/core/test_config.py`
- [ ] 创建 `backend/tests/core/test_adapters.py` (使用 Mock)
- [ ] 所有测试通过
- [ ] 测试覆盖率 > 80%



# 5. 错误码映射
HTTP 状态码 → 异常类

|HTTP 状态码 | 描述 | 异常类 | 重试 |
|------|------|------|------|
| 400 | 请求格式错误 | ConfigurationError | ❌ |
| 401 | 认证失败 | AuthenticationError | ❌ |
| 402 | 余额不足 | InsufficientBalanceError | ❌ |
| 429 | 速率限制 | RateLimitError | ✅ |
| 500 | 服务器错误 | ProviderConnectionError | ✅ |
| 502 | 网关错误 | ProviderConnectionError | ✅ |
| 503 | 服务不可用 | ModelUnavailableError | ✅ |
| 504 | 超时 | ProviderTimeoutError | ✅ |

# 6. 注意事项

- [ ] API Key 安全 - 绝不硬编码，通过环境变量管理，不在日志中输出
- [ ] 异步优先 - 所有 I/O 操作使用 async/await
- [ ] 错误映射完整 - 将 SDK 异常映射到自定义异常
- [ ] 流式响应健壮 - 处理连接中断、超时等情况
- [ ] 熔断器线程安全 - 使用 asyncio.Lock
- [ ] 超时配置合理 - LLM 响应可能较慢，默认 120 秒
- [ ] 可扩展性 - 新增供应商只需添加配置和适配器类

# 7. 下一阶段预告

完成本阶段后，进入 **Phase 4: 业务服务层**，将实现：
- [ ] ChatService: 聊天业务逻辑
- [ ] SessionService: 会话管理
- [ ] ModelService: 模型配置管理
- [ ] FileService: 文件上传处理

