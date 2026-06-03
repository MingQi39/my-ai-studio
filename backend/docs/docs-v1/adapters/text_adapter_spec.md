# DeepSeek API 适配器规范

---

## 1. 概述

本文档定义了 DeepSeek 官方直连 API 的适配器实现规范，用于指导多模型适配类的标准化开发。DeepSeek API 兼容 OpenAI API 格式，但具有独特的思考模式（Reasoning）和特定的错误码体系。

### 1.1 基本信息

| 属性 | 值 |
|------|-----|
| Provider | `deepseek` |
| Base URL | `https://api.deepseek.com` |
| API 兼容性 | OpenAI SDK 兼容 |
| 认证方式 | Bearer Token (API Key) |
| SDK 依赖 | `openai>=1.0.0` |

### 1.2 支持的模型

| 模型 ID | 描述 | 特性 |
|---------|------|------|
| `deepseek-chat` | 通用对话模型 | 基础对话、工具调用 |
| `deepseek-reasoner` | 推理模型 | 思维链输出、深度推理 |

---

## 2. 适配器架构设计

### 2.1 OpenAI 兼容性说明

DeepSeek、Qwen、Gemini、OpenRouter 等多家提供商均采用 **OpenAI 兼容 API** 格式。基础功能只需替换 `base_url` 和 `api_key` 即可使用：

```python
from openai import OpenAI

# DeepSeek
client = OpenAI(api_key="<KEY>", base_url="https://api.deepseek.com")

# Qwen (阿里云百炼)
client = OpenAI(api_key="<KEY>", base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")

# Gemini (Google)
client = OpenAI(api_key="<KEY>", base_url="https://generativelanguage.googleapis.com/v1beta/openai")

# OpenRouter
client = OpenAI(api_key="<KEY>", base_url="https://openrouter.ai/api/v1")
```

### 2.2 通用功能 vs 特殊功能

**通用功能（所有 OpenAI 兼容提供商）：**

| 功能 | 接口 | 说明 |
|------|------|------|
| 基础对话 | `chat.completions.create` | 标准消息格式 |
| 流式响应 | `stream=True` | SSE 格式 |
| 工具调用 | `tools` 参数 | Function Calling |
| 标准参数 | `temperature`, `max_tokens`, `top_p` | 通用参数 |

**特殊功能（各家差异）：**

| 提供商 | 特殊功能 | 实现方式 | 响应字段 |
|--------|----------|----------|----------|
| DeepSeek | 思考模式 | `model="deepseek-reasoner"` 或 `extra_body={"thinking": {...}}` | `reasoning_content` |
| Qwen | 思考模式 | `enable_thinking=True` 或 `extra_body={"enable_thinking": True}` | `reasoning_content` |
| Anthropic | 思考模式 | 独立 API 格式 | `thinking` 块 |

### 2.3 适配器继承架构

```
BaseLLMAdapter (抽象基类)
    │
    │   定义统一接口：
    │   - chat_completion()
    │   - list_models()
    │   - validate_credentials()
    │   - supports_feature()
    │
    ├── OpenAICompatibleAdapter (OpenAI 兼容适配器基类)
    │       │
    │       │   实现通用功能：
    │       │   - 基础对话
    │       │   - 流式响应
    │       │   - 工具调用
    │       │   - 错误处理
    │       │
    │       ├── DeepSeekAdapter
    │       │       扩展：思考模式 (reasoning_content)
    │       │
    │       ├── QwenAdapter
    │       │       扩展：思考模式 (enable_thinking)
    │       │
    │       ├── GeminiAdapter
    │       │       扩展：多模态处理
    │       │
    │       └── OpenRouterAdapter
    │               扩展：模型路由、provider 选择
    │
    ├── AnthropicAdapter (独立实现)
    │       完全不同的 API 格式
    │
    └── OllamaAdapter (本地模型)
            本地 API 格式
```

### 2.4 OpenAICompatibleAdapter 基类设计

```python
class OpenAICompatibleAdapter(BaseLLMAdapter):
    """OpenAI 兼容 API 适配器基类

    适用于所有兼容 OpenAI API 格式的提供商。
    子类只需覆写特殊功能的处理逻辑。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_id: str,
        timeout: int = 60,
    ):
        super().__init__(api_key, base_url, model_id, timeout)
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def chat_completion(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float | None = None,
        stream: bool = True,
        tools: list[dict] | None = None,
        **kwargs,  # 子类扩展参数
    ) -> AsyncIterator[ChatCompletionChunk] | dict:
        """通用聊天补全实现"""
        request_params = self._build_request_params(
            messages, temperature, max_tokens, top_p, stream, tools, **kwargs
        )

        if stream:
            return self._handle_stream_response(
                await self._client.chat.completions.create(**request_params)
            )
        else:
            return self._handle_response(
                await self._client.chat.completions.create(**request_params)
            )

    def _build_request_params(self, ...) -> dict:
        """构建请求参数，子类可覆写以添加特殊参数"""
        return {
            "model": self.model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stream": stream,
            "tools": tools,
        }

    async def _handle_stream_response(self, response) -> AsyncIterator[ChatCompletionChunk]:
        """处理流式响应，子类可覆写以处理特殊字段"""
        async for chunk in response:
            yield self._parse_chunk(chunk)

    def _parse_chunk(self, chunk) -> ChatCompletionChunk:
        """解析响应块，子类可覆写以处理特殊字段（如 reasoning_content）"""
        delta = chunk.choices[0].delta
        return ChatCompletionChunk(
            type="content",
            content=delta.content,
            thinking=None,
            tool_call=None,
            usage=None,
            error=None,
        )
```

---

## 3. DeepSeek 特殊功能规范

### 3.1 思考模式 (Reasoning Mode)

DeepSeek 支持思考模式，模型在输出最终回答前会先输出思维链内容。

#### 3.1.1 启用方式

**方式一：使用 `deepseek-reasoner` 模型**

```python
response = client.chat.completions.create(
    model="deepseek-reasoner",
    messages=messages,
    stream=True
)
```

**方式二：使用 `thinking` 参数**

```python
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    stream=True,
    extra_body={"thinking": {"type": "enabled"}}
)
```

#### 3.1.2 响应解析

思考模式下，响应包含两部分内容：

| 字段 | 类型 | 描述 |
|------|------|------|
| `reasoning_content` | `str` | 思维链内容（推理过程） |
| `content` | `str` | 最终回答 |

```python
# 流式响应解析
reasoning_content = ""
content = ""

for chunk in response:
    delta = chunk.choices[0].delta
    if delta.reasoning_content:
        reasoning_content += delta.reasoning_content
    elif delta.content:
        content += delta.content
```

#### 3.1.3 多轮对话处理

**重要规则：**

1. 在新一轮对话中，只传入上一轮的 `content`，忽略 `reasoning_content`
2. 建议在新 Turn 开始时清除历史消息中的 `reasoning_content` 以节省带宽

```python
# Turn 1 完成后
messages.append({"role": "assistant", "content": content})  # 只传 content

# Turn 2 开始前，清除历史 reasoning_content
def clear_reasoning_content(messages):
    for message in messages:
        if hasattr(message, 'reasoning_content'):
            message.reasoning_content = None
```

#### 3.1.4 DeepSeekAdapter 覆写实现

```python
class DeepSeekAdapter(OpenAICompatibleAdapter):
    """DeepSeek 适配器，扩展思考模式支持"""

    PROVIDER = "deepseek"
    DEFAULT_BASE_URL = "https://api.deepseek.com"

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model_id: str = "deepseek-chat",
        timeout: int = 120,
        enable_reasoning: bool = False,
    ):
        super().__init__(api_key, base_url or self.DEFAULT_BASE_URL, model_id, timeout)
        self.enable_reasoning = enable_reasoning

    def _build_request_params(self, ..., **kwargs) -> dict:
        """覆写：添加思考模式参数"""
        params = super()._build_request_params(...)

        # 如果启用思考模式且不是 reasoner 模型
        if self.enable_reasoning and self.model_id != "deepseek-reasoner":
            params["extra_body"] = {"thinking": {"type": "enabled"}}

        return params

    def _parse_chunk(self, chunk) -> ChatCompletionChunk:
        """覆写：处理 reasoning_content 字段"""
        delta = chunk.choices[0].delta

        # 检查是否有思维链内容
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

        # 标准内容
        return super()._parse_chunk(chunk)
```

---

## 4. 基础功能规范

### 4.1 基础对话 (Chat Completion)

#### 4.1.1 请求格式

```python
from openai import OpenAI

client = OpenAI(
    api_key="<DEEPSEEK_API_KEY>",
    base_url="https://api.deepseek.com"
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello"},
    ],
    stream=False,
    temperature=0.7,
    max_tokens=4096,
    top_p=1.0,
)
```

#### 4.1.2 响应格式

```python
# 非流式响应
response.choices[0].message.content  # str: 模型回复内容
response.usage.prompt_tokens         # int: 输入 token 数
response.usage.completion_tokens     # int: 输出 token 数
response.usage.total_tokens          # int: 总 token 数
```

#### 4.1.3 流式响应

```python
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    stream=True
)

for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### 4.2 工具调用 (Function Calling)

#### 4.2.1 工具定义格式

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather of a location for a specific date",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city name"
                    },
                    "date": {
                        "type": "string",
                        "description": "The date in format YYYY-mm-dd"
                    }
                },
                "required": ["location", "date"]
            }
        }
    }
]
```

#### 4.2.2 请求格式

```python
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    tools=tools,
    # 可选：启用思考模式
    extra_body={"thinking": {"type": "enabled"}}
)
```

#### 4.2.3 响应解析

```python
message = response.choices[0].message

# 获取各字段
reasoning_content = getattr(message, 'reasoning_content', None)  # 思维链（如启用）
content = message.content                                         # 文本回复
tool_calls = message.tool_calls                                   # 工具调用列表

# 工具调用结构
if tool_calls:
    for tool in tool_calls:
        tool.id                    # str: 工具调用 ID
        tool.function.name         # str: 函数名
        tool.function.arguments    # str: JSON 格式参数
```

#### 4.2.4 工具调用循环

```python
def run_tool_loop(messages, tools):
    while True:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools
        )

        message = response.choices[0].message
        messages.append(message)  # 保留完整 message（含 tool_calls）

        tool_calls = message.tool_calls

        # 无工具调用，返回最终结果
        if tool_calls is None:
            return message.content

        # 执行工具调用
        for tool in tool_calls:
            result = execute_tool(tool.function.name, tool.function.arguments)
            messages.append({
                "role": "tool",
                "tool_call_id": tool.id,
                "content": str(result)
            })
```

#### 4.2.5 工具调用 + 思考模式

当同时启用工具调用和思考模式时：

1. 每个子请求中携带该 Turn 下产生的 `reasoning_content`
2. 新 Turn 开始时清除历史 `reasoning_content`

```python
# 直接 append message 对象（包含所有字段）
messages.append(response.choices[0].message)

# 等价于：
messages.append({
    'role': 'assistant',
    'content': message.content,
    'reasoning_content': message.reasoning_content,
    'tool_calls': message.tool_calls,
})
```

---

## 5. 错误码规范

### 5.1 错误码映射表

| HTTP 状态码 | 错误描述 | 原因 | 映射异常类 | 处理策略 |
|-------------|----------|------|------------|----------|
| 400 | 格式错误 | 请求体格式错误 | `ConfigurationError` | 不重试，返回错误详情 |
| 401 | 认证失败 | API Key 错误 | `AuthenticationError` | 不重试，提示检查 Key |
| 402 | 余额不足 | 账号余额不足 | `InsufficientBalanceError` | 不重试，提示充值 |
| 422 | 参数错误 | 请求体参数错误 | `ConfigurationError` | 不重试，返回错误详情 |
| 429 | 速率限制 | TPM/RPM 达到上限 | `RateLimitError` | 指数退避重试 |
| 500 | 服务器故障 | 服务器内部故障 | `ProviderConnectionError` | 指数退避重试 |
| 503 | 服务器繁忙 | 服务器负载过高 | `ModelUnavailableError` | 指数退避重试 |

### 5.2 异常类定义

```python
# 新增：余额不足异常（DeepSeek 特有）
class InsufficientBalanceError(LLMException):
    def __init__(self, provider: str):
        super().__init__(
            message=f"Insufficient balance for provider: {provider}",
            error_code="INSUFFICIENT_BALANCE",
            details={"provider": provider},
            status_code=402
        )
        self.provider = provider
```

### 5.3 错误处理实现

```python
from openai import APIError, AuthenticationError as OpenAIAuthError

def handle_openai_compatible_error(error: Exception, provider: str) -> LLMException:
    """将 OpenAI 兼容 SDK 异常映射到自定义异常（通用实现）"""

    if isinstance(error, OpenAIAuthError):
        return AuthenticationError(provider=provider)

    if isinstance(error, APIError):
        status_code = error.status_code

        if status_code == 400:
            return ConfigurationError(
                config_key="request_body",
                reason=str(error.message)
            )
        elif status_code == 402:
            # DeepSeek 特有
            return InsufficientBalanceError(provider=provider)
        elif status_code == 422:
            return ConfigurationError(
                config_key="parameters",
                reason=str(error.message)
            )
        elif status_code == 429:
            return RateLimitError(
                retry_after=int(error.response.headers.get("Retry-After", 60))
            )
        elif status_code == 500:
            return ProviderConnectionError(
                provider=provider,
                endpoint=error.request.url if error.request else "unknown"
            )
        elif status_code == 503:
            return ModelUnavailableError(
                model_id="unknown",
                reason="Server overloaded"
            )

    # 默认：连接错误
    return ProviderConnectionError(
        provider=provider,
        endpoint="unknown"
    )
```

### 5.4 重试策略

```python
OPENAI_COMPATIBLE_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    base_delay=1.0,
    max_delay=60.0,
    strategy=RetryStrategy.EXPONENTIAL,
    jitter=True,
    retryable_exceptions=(
        RateLimitError,
        ProviderConnectionError,
        ModelUnavailableError,
        ProviderTimeoutError,
    )
)
```

---

## 6. 适配器接口定义

### 6.1 DeepSeek 适配器完整定义

```python
class DeepSeekAdapter(OpenAICompatibleAdapter):
    """DeepSeek API 适配器

    继承 OpenAICompatibleAdapter，扩展 DeepSeek 特有的思考模式。
    """

    PROVIDER = "deepseek"
    DEFAULT_BASE_URL = "https://api.deepseek.com"

    # 支持的模型
    SUPPORTED_MODELS = {
        "deepseek-chat": ModelInfo(
            id="deepseek-chat",
            name="DeepSeek Chat",
            context_length=64000,
            supports_vision=False,
            supports_tools=True,
            supports_reasoning=True,
        ),
        "deepseek-reasoner": ModelInfo(
            id="deepseek-reasoner",
            name="DeepSeek Reasoner",
            context_length=64000,
            supports_vision=False,
            supports_tools=True,
            supports_reasoning=True,  # 默认启用
        ),
    }

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model_id: str = "deepseek-chat",
        timeout: int = 120,
        enable_reasoning: bool = False,
    ):
        """初始化 DeepSeek 适配器

        Args:
            api_key: DeepSeek API Key
            base_url: API 基础 URL，默认为官方地址
            model_id: 模型 ID
            timeout: 请求超时时间（秒）
            enable_reasoning: 是否启用思考模式（对 deepseek-chat 有效）
        """
        super().__init__(api_key, base_url or self.DEFAULT_BASE_URL, model_id, timeout)
        self.enable_reasoning = enable_reasoning

    async def list_models(self) -> list[ModelInfo]:
        """列出可用模型"""
        return list(self.SUPPORTED_MODELS.values())

    def supports_feature(self, feature: str) -> bool:
        """检查是否支持特定功能"""
        model_info = self.SUPPORTED_MODELS.get(self.model_id)
        if not model_info:
            return False

        feature_map = {
            "vision": model_info.supports_vision,
            "tools": model_info.supports_tools,
            "reasoning": model_info.supports_reasoning,
            "streaming": True,
        }
        return feature_map.get(feature, False)
```

### 6.2 流式响应 Chunk 格式

```python
# 思维链内容
ChatCompletionChunk(
    type="thinking",
    content=None,
    thinking="Let me analyze this step by step...",
    tool_call=None,
    usage=None,
    error=None,
)

# 文本内容
ChatCompletionChunk(
    type="content",
    content="The answer is...",
    thinking=None,
    tool_call=None,
    usage=None,
    error=None,
)

# 工具调用
ChatCompletionChunk(
    type="tool_call",
    content=None,
    thinking=None,
    tool_call={
        "id": "call_xxx",
        "name": "get_weather",
        "arguments": '{"location": "Beijing", "date": "2025-01-23"}'
    },
    usage=None,
    error=None,
)

# 完成信号
ChatCompletionChunk(
    type="done",
    content=None,
    thinking=None,
    tool_call=None,
    usage={
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "reasoning_tokens": 200,  # 思考模式特有
    },
    error=None,
)
```

---

## 7. 配置项

### 7.1 环境变量

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | - |
| `DEEPSEEK_BASE_URL` | API 基础 URL | `https://api.deepseek.com` |
| `DEEPSEEK_TIMEOUT` | 请求超时（秒） | `120` |
| `DEEPSEEK_MAX_RETRIES` | 最大重试次数 | `3` |

### 7.2 模型默认参数

```python
DEEPSEEK_DEFAULT_PARAMS = {
    "temperature": 0.7,
    "max_tokens": 4096,
    "top_p": 1.0,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
}
```

---

## 8. 适配器工厂配置

```python
class LLMAdapterFactory:
    """LLM 适配器工厂"""

    _adapters: dict[LLMProvider, type[BaseLLMAdapter]] = {
        # OpenAI 兼容适配器
        LLMProvider.openai: OpenAICompatibleAdapter,
        LLMProvider.deepseek: DeepSeekAdapter,
        LLMProvider.qwen: QwenAdapter,
        LLMProvider.gemini: GeminiAdapter,
        LLMProvider.openrouter: OpenRouterAdapter,
        LLMProvider.local: OpenAICompatibleAdapter,

        # 独立适配器
        LLMProvider.anthropic: AnthropicAdapter,
        LLMProvider.ollama: OllamaAdapter,
    }

    _default_base_urls: dict[LLMProvider, str] = {
        LLMProvider.openai: "https://api.openai.com/v1",
        LLMProvider.deepseek: "https://api.deepseek.com",
        LLMProvider.qwen: "https://dashscope.aliyuncs.com/compatible-mode/v1",
        LLMProvider.gemini: "https://generativelanguage.googleapis.com/v1beta/openai",
        LLMProvider.openrouter: "https://openrouter.ai/api/v1",
        LLMProvider.anthropic: "https://api.anthropic.com",
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
        """创建适配器实例"""
        adapter_class = cls._adapters.get(provider)
        if not adapter_class:
            raise ValueError(f"Unsupported provider: {provider}")

        return adapter_class(
            api_key=api_key,
            base_url=base_url or cls._default_base_urls.get(provider),
            model_id=model_id,
            **kwargs
        )
```

---

## 9. 测试用例

### 9.1 单元测试清单

- [ ] `test_basic_chat_completion`: 基础对话测试
- [ ] `test_streaming_response`: 流式响应测试
- [ ] `test_reasoning_mode_with_model`: 使用 deepseek-reasoner 模型测试
- [ ] `test_reasoning_mode_with_param`: 使用 thinking 参数测试
- [ ] `test_multi_turn_reasoning`: 多轮思考模式对话测试
- [ ] `test_tool_calling_basic`: 基础工具调用测试
- [ ] `test_tool_calling_multi_step`: 多步工具调用测试
- [ ] `test_tool_calling_with_reasoning`: 工具调用 + 思考模式测试
- [ ] `test_error_handling_401`: 认证失败错误处理
- [ ] `test_error_handling_402`: 余额不足错误处理
- [ ] `test_error_handling_429`: 速率限制错误处理
- [ ] `test_error_handling_500`: 服务器错误处理
- [ ] `test_retry_on_rate_limit`: 速率限制重试测试
- [ ] `test_validate_credentials`: 凭证验证测试

### 9.2 集成测试

测试脚本位置：`backend/tests/deepseek_test/test_deepseek.py`

---

## 10. 注意事项

1. **思考模式 Token 消耗**：思考模式会产生额外的 `reasoning_tokens`，需在 usage 统计中体现
2. **超时设置**：推理模型响应较慢，建议超时设置 >= 120 秒
3. **多轮对话**：新 Turn 开始时清除历史 `reasoning_content` 以节省带宽
4. **工具调用循环**：单个 Turn 内可能有多次工具调用，需循环处理直到无 `tool_calls`
5. **API Key 安全**：不要在日志中输出 API Key
6. **流式中断处理**：需处理流式响应中途断开的情况
7. **适配器复用**：基础功能通过 `OpenAICompatibleAdapter` 复用，子类只覆写特殊功能

---

## 11. 参考资料

- [DeepSeek API 官方文档](https://platform.deepseek.com/api-docs)
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [阿里云百炼 Qwen API](https://help.aliyun.com/zh/model-studio/developer-reference/use-qwen-by-calling-api)
- 项目适配器基类：`backend/app/core/adapters/base.py`
