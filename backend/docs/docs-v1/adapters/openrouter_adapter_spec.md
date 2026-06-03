# OpenRouter API 适配器规范

---

## 1. 概述

本文档定义了 OpenRouter 第三方中转平台的适配器实现规范。OpenRouter 是一个统一的 LLM API 网关，支持通过单一 API Key 访问多家提供商的模型，包括 OpenAI、Anthropic、Google、Meta 等。

### 1.1 基本信息

| 属性 | 值 |
|------|-----|
| Provider | `openrouter` |
| Base URL | `https://openrouter.ai/api/v1` |
| API 兼容性 | OpenAI SDK 兼容 |
| 认证方式 | Bearer Token (API Key) |
| SDK 依赖 | `openai>=1.0.0` |

### 1.2 核心优势

- **统一接口**：一个 API Key 访问多家模型
- **模型切换**：只需更改 `model` 参数即可切换不同提供商的模型
- **成本优化**：自动选择最优价格的提供商
- **高可用性**：自动故障转移到备用提供商

### 1.3 支持的模型提供商

| 提供商 | 模型前缀 | 示例模型 |
|--------|----------|----------|
| Google | `google/` | `google/gemini-2.5-pro-preview`, `google/gemini-2.0-flash-001` |
| OpenAI | `openai/` | `openai/gpt-4o`, `openai/gpt-4o-mini` |
| Anthropic | `anthropic/` | `anthropic/claude-3.5-sonnet`, `anthropic/claude-3.5-haiku` |
| Meta | `meta-llama/` | `meta-llama/llama-3.3-70b-instruct` |
| DeepSeek | `deepseek/` | `deepseek/deepseek-chat`, `deepseek/deepseek-reasoner` |
| Qwen | `qwen/` | `qwen/qwen-2.5-72b-instruct` |

---

## 2. 基础功能

### 2.1 基础对话

```python
from openai import OpenAI

client = OpenAI(
    api_key="<OPENROUTER_API_KEY>",
    base_url="https://openrouter.ai/api/v1"
)

response = client.chat.completions.create(
    model="google/gemini-2.0-flash-001",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ],
    stream=False
)

print(response.choices[0].message.content)
```

### 2.2 流式响应

```python
response = client.chat.completions.create(
    model="google/gemini-2.0-flash-001",
    messages=[{"role": "user", "content": "Write a poem."}],
    stream=True
)

for chunk in response:
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

### 2.3 多模型切换

OpenRouter 的核心优势是可以通过更改 `model` 参数轻松切换不同模型：

```python
# 使用 Google Gemini
response = client.chat.completions.create(
    model="google/gemini-2.5-pro-preview",
    messages=[{"role": "user", "content": "Hello"}]
)

# 切换到 Anthropic Claude
response = client.chat.completions.create(
    model="anthropic/claude-3.5-sonnet",
    messages=[{"role": "user", "content": "Hello"}]
)

# 切换到 OpenAI GPT-4
response = client.chat.completions.create(
    model="openai/gpt-4o",
    messages=[{"role": "user", "content": "Hello"}]
)
```

---

## 3. 推理模式 (Reasoning)

### 3.1 启用推理模式

OpenRouter 通过 `extra_body` 参数启用推理模式：

```python
response = client.chat.completions.create(
    model="google/gemini-2.5-pro-preview",
    messages=[
        {
            "role": "user",
            "content": "How many r's are in the word 'strawberry'?"
        }
    ],
    extra_body={"reasoning": {"enabled": True}}
)

message = response.choices[0].message
print(f"回答: {message.content}")

# 获取推理详情
reasoning_details = getattr(message, "reasoning_details", None)
if reasoning_details:
    print(f"推理过程: {reasoning_details}")
```

### 3.2 多轮对话保留推理上下文

在多轮对话中，需要将 `reasoning_details` 传回以保持推理连续性：

```python
# 第一轮对话
response = client.chat.completions.create(
    model="google/gemini-2.5-pro-preview",
    messages=[
        {"role": "user", "content": "How many r's are in the word 'strawberry'?"}
    ],
    extra_body={"reasoning": {"enabled": True}}
)

first_message = response.choices[0].message

# 构建第二轮消息，保留 reasoning_details
messages = [
    {"role": "user", "content": "How many r's are in the word 'strawberry'?"},
    {
        "role": "assistant",
        "content": first_message.content,
        "reasoning_details": first_message.reasoning_details  # 传回推理详情
    },
    {"role": "user", "content": "Are you sure? Think carefully."}
]

# 第二轮对话 - 模型从上次推理继续
response2 = client.chat.completions.create(
    model="google/gemini-2.5-pro-preview",
    messages=messages,
    extra_body={"reasoning": {"enabled": True}}
)
```

### 3.3 推理模式参数

| 参数 | 类型 | 描述 |
|------|------|------|
| `reasoning.enabled` | `bool` | 是否启用推理模式 |
| `reasoning.max_tokens` | `int` | 推理过程最大 token 数（可选） |

---

## 4. 视觉理解

### 4.1 图片 URL 输入

```python
response = client.chat.completions.create(
    model="google/gemini-2.0-flash-001",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://example.com/image.jpg"
                    }
                },
                {
                    "type": "text",
                    "text": "What's in this image?"
                }
            ]
        }
    ]
)
```

### 4.2 Base64 图片输入

```python
import base64

with open("image.jpg", "rb") as f:
    base64_image = base64.b64encode(f.read()).decode("utf-8")

response = client.chat.completions.create(
    model="google/gemini-2.0-flash-001",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                },
                {"type": "text", "text": "Describe this image."}
            ]
        }
    ]
)
```

### 4.3 支持视觉的模型

| 模型 | 视觉支持 | 推理支持 |
|------|----------|----------|
| `google/gemini-2.0-flash-001` | ✅ | ❌ |
| `google/gemini-2.5-pro-preview` | ✅ | ✅ |
| `openai/gpt-4o` | ✅ | ❌ |
| `anthropic/claude-3.5-sonnet` | ✅ | ❌ |

---

## 5. 图像生成

### 5.1 生成图像

部分模型支持图像生成，需要通过 `modalities` 参数启用：

```python
response = client.chat.completions.create(
    model="google/gemini-2.0-flash-exp:free",
    messages=[
        {
            "role": "user",
            "content": "Generate a beautiful sunset over mountains"
        }
    ],
    extra_body={"modalities": ["image", "text"]}
)

message = response.choices[0].message

# 检查生成的图像
if hasattr(message, "images") and message.images:
    for image in message.images:
        image_url = image["image_url"]["url"]  # Base64 data URL
        print(f"Generated image: {image_url[:50]}...")
```

### 5.2 图像生成参数

| 参数 | 类型 | 描述 |
|------|------|------|
| `modalities` | `list[str]` | 输出模态，如 `["image", "text"]` |

---

## 6. 适配器架构

### 6.1 继承关系

```
OpenAICompatibleAdapter
    │
    └── OpenRouterAdapter
            │
            ├── 支持动态模型切换
            ├── 支持推理模式 (reasoning)
            ├── 支持图像生成 (modalities)
            └── 支持多提供商路由
```

### 6.2 OpenRouterAdapter 实现

```python
class OpenRouterAdapter(OpenAICompatibleAdapter):
    """OpenRouter API 适配器

    支持通过单一 API Key 访问多家模型提供商。
    """

    PROVIDER = "openrouter"
    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

    # 模型能力映射（动态获取或预定义常用模型）
    MODEL_CAPABILITIES = {
        "google/gemini-2.5-pro-preview": {
            "supports_vision": True,
            "supports_tools": True,
            "supports_reasoning": True,
            "supports_image_generation": False,
        },
        "google/gemini-2.0-flash-001": {
            "supports_vision": True,
            "supports_tools": True,
            "supports_reasoning": False,
            "supports_image_generation": False,
        },
        "google/gemini-2.0-flash-exp:free": {
            "supports_vision": True,
            "supports_tools": True,
            "supports_reasoning": False,
            "supports_image_generation": True,
        },
        "openai/gpt-4o": {
            "supports_vision": True,
            "supports_tools": True,
            "supports_reasoning": False,
            "supports_image_generation": False,
        },
        "anthropic/claude-3.5-sonnet": {
            "supports_vision": True,
            "supports_tools": True,
            "supports_reasoning": False,
            "supports_image_generation": False,
        },
    }

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model_id: str = "google/gemini-2.0-flash-001",
        timeout: int = 120,
        enable_reasoning: bool = False,
        modalities: list[str] | None = None,
    ):
        """初始化 OpenRouter 适配器

        Args:
            api_key: OpenRouter API Key
            base_url: API 基础 URL
            model_id: 模型 ID（格式：provider/model-name）
            timeout: 请求超时时间（秒）
            enable_reasoning: 是否启用推理模式
            modalities: 输出模态列表，如 ["image", "text"]
        """
        super().__init__(api_key, base_url or self.DEFAULT_BASE_URL, model_id, timeout)
        self.enable_reasoning = enable_reasoning
        self.modalities = modalities

    def _build_request_params(self, messages, ..., **kwargs) -> dict:
        """覆写：添加 OpenRouter 特殊参数"""
        params = super()._build_request_params(messages, ...)

        extra_body = {}

        # 推理模式
        if self.enable_reasoning or kwargs.get("enable_reasoning"):
            extra_body["reasoning"] = {"enabled": True}

        # 输出模态（图像生成）
        if self.modalities or kwargs.get("modalities"):
            extra_body["modalities"] = self.modalities or kwargs.get("modalities")

        if extra_body:
            params["extra_body"] = extra_body

        return params

    def _parse_chunk(self, chunk) -> ChatCompletionChunk:
        """覆写：处理推理内容和图像"""
        delta = chunk.choices[0].delta

        # 检查推理内容
        reasoning = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
        if reasoning:
            return ChatCompletionChunk(
                type="thinking",
                content=None,
                thinking=reasoning,
                tool_call=None,
                usage=None,
                error=None,
            )

        return super()._parse_chunk(chunk)

    def _parse_response(self, response) -> dict:
        """覆写：处理非流式响应中的推理详情和图像"""
        message = response.choices[0].message

        result = {
            "content": message.content,
            "tool_calls": message.tool_calls,
            "reasoning_details": getattr(message, "reasoning_details", None),
            "images": getattr(message, "images", None),
            "usage": response.usage,
        }

        return result

    def switch_model(self, model_id: str):
        """动态切换模型"""
        self.model_id = model_id

    async def list_models(self) -> list[dict]:
        """获取可用模型列表"""
        # OpenRouter 提供 /models 端点
        response = await self._client.get("/models")
        return response.json().get("data", [])

    def supports_feature(self, feature: str) -> bool:
        """检查当前模型是否支持特定功能"""
        capabilities = self.MODEL_CAPABILITIES.get(self.model_id, {})
        feature_map = {
            "vision": capabilities.get("supports_vision", False),
            "tools": capabilities.get("supports_tools", False),
            "reasoning": capabilities.get("supports_reasoning", False),
            "image_generation": capabilities.get("supports_image_generation", False),
            "streaming": True,
        }
        return feature_map.get(feature, False)
```

---

## 7. 错误处理

### 7.1 OpenRouter 特有错误

| HTTP 状态码 | 错误描述 | 原因 | 处理策略 |
|-------------|----------|------|----------|
| 400 | Bad Request | 请求格式错误 | 不重试 |
| 401 | Unauthorized | API Key 无效 | 不重试 |
| 402 | Payment Required | 余额不足 | 不重试 |
| 403 | Forbidden | 模型访问被拒绝 | 不重试 |
| 429 | Rate Limited | 请求频率过高 | 指数退避重试 |
| 502 | Bad Gateway | 上游提供商错误 | 重试或切换模型 |
| 503 | Service Unavailable | 服务不可用 | 重试 |

### 7.2 错误处理实现

```python
def handle_openrouter_error(error: Exception) -> LLMException:
    """将 OpenRouter 错误映射到自定义异常"""

    if isinstance(error, APIError):
        status_code = error.status_code

        if status_code == 402:
            return InsufficientBalanceError(provider="openrouter")
        elif status_code == 403:
            return ModelUnavailableError(
                model_id=error.body.get("model", "unknown"),
                reason="Access denied"
            )
        elif status_code == 502:
            # 上游提供商错误，可以尝试切换模型
            return ProviderConnectionError(
                provider="openrouter",
                endpoint=error.request.url if error.request else "unknown"
            )

    return handle_openai_compatible_error(error, "openrouter")
```

---

## 8. 配置项

### 8.1 环境变量

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `OPENROUTER_API_KEY` | OpenRouter API Key | - |
| `OPENROUTER_BASE_URL` | API 基础 URL | `https://openrouter.ai/api/v1` |
| `OPENROUTER_TIMEOUT` | 请求超时（秒） | `120` |
| `OPENROUTER_DEFAULT_MODEL` | 默认模型 | `google/gemini-2.0-flash-001` |

### 8.2 请求头配置

OpenRouter 支持额外的请求头用于追踪和优化：

```python
# 可选请求头
headers = {
    "HTTP-Referer": "https://your-app.com",  # 用于追踪
    "X-Title": "Your App Name",               # 应用名称
}
```

---

## 9. 适配器工厂配置

```python
class LLMAdapterFactory:
    """LLM 适配器工厂"""

    _adapters: dict[LLMProvider, type[BaseLLMAdapter]] = {
        # ...其他适配器
        LLMProvider.openrouter: OpenRouterAdapter,
    }

    _default_base_urls: dict[LLMProvider, str] = {
        # ...其他 URL
        LLMProvider.openrouter: "https://openrouter.ai/api/v1",
    }

    # OpenRouter 支持的模型前缀
    OPENROUTER_PROVIDERS = [
        "google/",
        "openai/",
        "anthropic/",
        "meta-llama/",
        "deepseek/",
        "qwen/",
        "mistralai/",
        "cohere/",
    ]
```

---

## 10. 测试用例

### 10.1 单元测试清单

- [ ] `test_basic_chat`: 基础对话测试
- [ ] `test_streaming`: 流式响应测试
- [ ] `test_reasoning_mode`: 推理模式测试
- [ ] `test_multi_turn_reasoning`: 多轮推理对话测试
- [ ] `test_vision_url`: URL 图片视觉理解
- [ ] `test_vision_base64`: Base64 图片视觉理解
- [ ] `test_image_generation`: 图像生成测试
- [ ] `test_model_switching`: 模型切换测试
- [ ] `test_tool_calling`: 工具调用测试
- [ ] `test_error_handling`: 错误处理测试

### 10.2 集成测试

测试脚本位置：`backend/tests/openrouter_test/test_openrouter.py`

---

## 11. 注意事项

1. **模型命名**：OpenRouter 模型 ID 格式为 `provider/model-name`，如 `google/gemini-2.5-pro-preview`
2. **推理模式兼容性**：并非所有模型都支持推理模式，需检查模型能力
3. **图像生成**：仅部分模型支持，需要设置 `modalities` 参数
4. **多轮推理**：保留 `reasoning_details` 以维持推理连续性
5. **成本控制**：不同模型价格差异大，建议根据任务选择合适模型
6. **故障转移**：OpenRouter 会自动处理提供商故障，但可能切换到不同提供商
7. **速率限制**：受 OpenRouter 和上游提供商双重限制

---

## 12. 常用模型推荐

### 12.1 按场景推荐

| 场景 | 推荐模型 | 原因 |
|------|----------|------|
| 日常对话 | `google/gemini-2.0-flash-001` | 快速、便宜 |
| 复杂推理 | `google/gemini-2.5-pro-preview` | 支持推理模式 |
| 代码生成 | `anthropic/claude-3.5-sonnet` | 代码能力强 |
| 视觉理解 | `openai/gpt-4o` | 视觉能力强 |
| 长文本 | `google/gemini-2.5-pro-preview` | 上下文窗口大 |
| 成本敏感 | `meta-llama/llama-3.3-70b-instruct` | 开源模型，价格低 |

### 12.2 免费模型

OpenRouter 提供部分免费模型（带 `:free` 后缀）：

- `google/gemini-2.0-flash-exp:free`
- `meta-llama/llama-3.2-3b-instruct:free`
- `qwen/qwen-2-7b-instruct:free`

---

## 13. 参考资料

- [OpenRouter 官方文档](https://openrouter.ai/docs)
- [OpenRouter 模型列表](https://openrouter.ai/models)
- [OpenRouter API 参考](https://openrouter.ai/docs/api-reference)
- 项目适配器基类：`backend/app/core/adapters/base.py`
