# 视觉语言模型 (VLM) 适配器规范

---

## 1. 概述

本文档定义了视觉语言模型（Vision-Language Model, VLM）的适配器实现规范。VLM 能够同时处理图像和文本输入，实现图像理解、图文问答等功能。

### 1.1 支持的提供商

| 提供商 | 模型系列 | API 兼容性 | 特殊功能 |
|--------|----------|------------|----------|
| Qwen (阿里云) | qwen-vl-plus, qwen3-vl-plus | OpenAI 兼容 | 思考模式 |
| OpenAI | gpt-4-vision, gpt-4o | 原生 | - |
| Anthropic | claude-3-* | 独立格式 | - |
| Gemini | gemini-pro-vision | OpenAI 兼容 | - |

### 1.2 Qwen VL 基本信息

| 属性 | 值 |
|------|-----|
| Provider | `qwen` |
| Base URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| API 兼容性 | OpenAI SDK 兼容 |
| 认证方式 | Bearer Token (API Key) |
| SDK 依赖 | `openai>=1.0.0` |

### 1.3 Qwen VL 支持的模型

| 模型 ID | 描述 | 特性 |
|---------|------|------|
| `qwen-vl-plus` | 通用视觉语言模型 | 图像理解、多图对比 |
| `qwen-vl-max` | 高性能视觉语言模型 | 更强的图像理解能力 |
| `qwen3-vl-plus` | Qwen3 视觉语言模型 | 支持思考模式 |
| `qwen3-vl-max` | Qwen3 高性能视觉模型 | 支持思考模式 |

---

## 2. 图像输入格式

### 2.1 消息结构

VLM 使用多模态消息格式，`content` 字段为数组，包含多个内容块：

```python
messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    "url": "<图片URL或Base64>"
                }
            },
            {
                "type": "text",
                "text": "请描述这张图片"
            }
        ]
    }
]
```

### 2.2 图像输入方式

#### 2.2.1 URL 方式

```python
{
    "type": "image_url",
    "image_url": {
        "url": "https://example.com/image.jpg"
    }
}
```

**支持的 URL 类型：**
- HTTP/HTTPS URL
- 阿里云 OSS URL
- 其他公开可访问的图片 URL

#### 2.2.2 Base64 方式

```python
import base64

# 读取本地图片并转换为 Base64
with open("image.jpg", "rb") as f:
    base64_image = base64.b64encode(f.read()).decode("utf-8")

{
    "type": "image_url",
    "image_url": {
        "url": f"data:image/jpeg;base64,{base64_image}"
    }
}
```

**支持的 MIME 类型：**
- `image/jpeg`
- `image/png`
- `image/gif`
- `image/webp`

### 2.3 多图输入

```python
messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/image1.jpg"}
            },
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/image2.jpg"}
            },
            {
                "type": "text",
                "text": "请比较这两张图片的异同"
            }
        ]
    }
]
```

---

## 3. 功能规范

### 3.1 基础视觉理解

```python
from openai import OpenAI

client = OpenAI(
    api_key="<DASHSCOPE_API_KEY>",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

response = client.chat.completions.create(
    model="qwen-vl-plus",
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
                {"type": "text", "text": "请描述这张图片的内容"}
            ]
        }
    ],
    stream=False
)

print(response.choices[0].message.content)
```

### 3.2 视觉理解 + 思考模式

Qwen3-VL 系列支持思考模式，在回答前输出推理过程：

```python
response = client.chat.completions.create(
    model="qwen3-vl-plus",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://example.com/math_problem.jpg"
                    }
                },
                {"type": "text", "text": "这道题怎么解答？"}
            ]
        }
    ],
    stream=True,
    extra_body={
        "enable_thinking": True,
        "thinking_budget": 4096  # 限制思考 token 数
    },
    stream_options={"include_usage": True}
)

reasoning_content = ""
answer_content = ""
is_answering = False

for chunk in response:
    if not chunk.choices:
        # 最后一个 chunk 包含 usage 信息
        print(f"Token 使用: {chunk.usage}")
    else:
        delta = chunk.choices[0].delta

        # 思考过程
        if hasattr(delta, "reasoning_content") and delta.reasoning_content:
            reasoning_content += delta.reasoning_content
            print(delta.reasoning_content, end="", flush=True)
        # 最终回答
        elif delta.content:
            if not is_answering:
                print("\n--- 回答 ---\n")
                is_answering = True
            answer_content += delta.content
            print(delta.content, end="", flush=True)
```

### 3.3 视觉理解 + 工具调用

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_product",
            "description": "根据商品描述搜索商品信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {"type": "string", "description": "商品名称"},
                    "category": {"type": "string", "description": "商品类别"}
                },
                "required": ["product_name"]
            }
        }
    }
]

response = client.chat.completions.create(
    model="qwen-vl-plus",
    messages=[
        {
            "role": "system",
            "content": "你是一个购物助手，可以识别图片中的商品并帮助用户搜索。"
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": "https://example.com/product.jpg"}
                },
                {"type": "text", "text": "帮我搜索图片中的商品"}
            ]
        }
    ],
    tools=tools,
    stream=False
)

message = response.choices[0].message
if message.tool_calls:
    for tool in message.tool_calls:
        print(f"工具调用: {tool.function.name}")
        print(f"参数: {tool.function.arguments}")
```

---

## 4. 适配器架构

### 4.1 继承关系

```
OpenAICompatibleAdapter
    │
    └── QwenAdapter
            │
            └── 支持视觉模型检测
            └── 支持思考模式 (enable_thinking)
```

### 4.2 QwenVisionAdapter 实现

```python
class QwenAdapter(OpenAICompatibleAdapter):
    """Qwen 适配器，支持文本和视觉模型"""

    PROVIDER = "qwen"
    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    SUPPORTED_MODELS = {
        # 文本模型
        "qwen-plus": ModelInfo(
            id="qwen-plus",
            name="Qwen Plus",
            context_length=131072,
            supports_vision=False,
            supports_tools=True,
            supports_reasoning=False,
        ),
        "qwen3-plus": ModelInfo(
            id="qwen3-plus",
            name="Qwen3 Plus",
            context_length=131072,
            supports_vision=False,
            supports_tools=True,
            supports_reasoning=True,
        ),
        # 视觉模型
        "qwen-vl-plus": ModelInfo(
            id="qwen-vl-plus",
            name="Qwen VL Plus",
            context_length=32768,
            supports_vision=True,
            supports_tools=True,
            supports_reasoning=False,
        ),
        "qwen3-vl-plus": ModelInfo(
            id="qwen3-vl-plus",
            name="Qwen3 VL Plus",
            context_length=32768,
            supports_vision=True,
            supports_tools=True,
            supports_reasoning=True,
        ),
    }

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model_id: str = "qwen-plus",
        timeout: int = 120,
        enable_thinking: bool = False,
        thinking_budget: int | None = None,
    ):
        super().__init__(api_key, base_url or self.DEFAULT_BASE_URL, model_id, timeout)
        self.enable_thinking = enable_thinking
        self.thinking_budget = thinking_budget

    def _build_request_params(self, messages, ..., **kwargs) -> dict:
        """覆写：添加思考模式参数"""
        params = super()._build_request_params(messages, ...)

        # 如果启用思考模式
        if self.enable_thinking:
            extra_body = {"enable_thinking": True}
            if self.thinking_budget:
                extra_body["thinking_budget"] = self.thinking_budget
            params["extra_body"] = extra_body

        return params

    def _parse_chunk(self, chunk) -> ChatCompletionChunk:
        """覆写：处理 reasoning_content 字段"""
        delta = chunk.choices[0].delta

        # 检查是否有思维链内容
        reasoning_content = getattr(delta, "reasoning_content", None)
        if reasoning_content:
            return ChatCompletionChunk(
                type="thinking",
                content=None,
                thinking=reasoning_content,
                tool_call=None,
                usage=None,
                error=None,
            )

        return super()._parse_chunk(chunk)

    def is_vision_model(self) -> bool:
        """检查当前模型是否为视觉模型"""
        model_info = self.SUPPORTED_MODELS.get(self.model_id)
        return model_info.supports_vision if model_info else False
```

---

## 5. 消息格式转换

### 5.1 统一消息格式

适配器内部使用统一的消息格式，支持文本和图像混合：

```python
class ContentBlock(TypedDict):
    type: Literal["text", "image_url", "image_base64"]
    text: str | None
    image_url: str | None
    image_base64: str | None
    mime_type: str | None  # 用于 base64 图片

class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[ContentBlock]  # 支持多模态
```

### 5.2 格式转换函数

```python
def convert_to_openai_format(messages: list[ChatMessage]) -> list[dict]:
    """将统一格式转换为 OpenAI 兼容格式"""
    result = []

    for msg in messages:
        if isinstance(msg["content"], str):
            # 纯文本消息
            result.append(msg)
        else:
            # 多模态消息
            content_blocks = []
            for block in msg["content"]:
                if block["type"] == "text":
                    content_blocks.append({
                        "type": "text",
                        "text": block["text"]
                    })
                elif block["type"] == "image_url":
                    content_blocks.append({
                        "type": "image_url",
                        "image_url": {"url": block["image_url"]}
                    })
                elif block["type"] == "image_base64":
                    mime_type = block.get("mime_type", "image/jpeg")
                    content_blocks.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{block['image_base64']}"
                        }
                    })

            result.append({
                "role": msg["role"],
                "content": content_blocks
            })

    return result
```

---

## 6. 图像处理工具

### 6.1 图像预处理

```python
import base64
from PIL import Image
from io import BytesIO

class ImageProcessor:
    """图像预处理工具"""

    MAX_SIZE = (2048, 2048)  # 最大尺寸
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    @staticmethod
    def load_from_url(url: str) -> bytes:
        """从 URL 加载图片"""
        import urllib.request
        with urllib.request.urlopen(url) as response:
            return response.read()

    @staticmethod
    def load_from_file(file_path: str) -> bytes:
        """从文件加载图片"""
        with open(file_path, "rb") as f:
            return f.read()

    @staticmethod
    def to_base64(image_data: bytes) -> str:
        """转换为 Base64"""
        return base64.b64encode(image_data).decode("utf-8")

    @staticmethod
    def resize_if_needed(image_data: bytes, max_size: tuple = MAX_SIZE) -> bytes:
        """如果图片过大则缩放"""
        img = Image.open(BytesIO(image_data))

        if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            buffer = BytesIO()
            img.save(buffer, format=img.format or "JPEG")
            return buffer.getvalue()

        return image_data

    @staticmethod
    def get_mime_type(image_data: bytes) -> str:
        """检测图片 MIME 类型"""
        if image_data[:8] == b'\x89PNG\r\n\x1a\n':
            return "image/png"
        elif image_data[:2] == b'\xff\xd8':
            return "image/jpeg"
        elif image_data[:6] in (b'GIF87a', b'GIF89a'):
            return "image/gif"
        elif image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
            return "image/webp"
        else:
            return "image/jpeg"  # 默认
```

---

## 7. 错误处理

### 7.1 视觉模型特有错误

| 错误类型 | 原因 | 处理方式 |
|----------|------|----------|
| 图片无法访问 | URL 无效或无权限 | 返回 `ImageAccessError` |
| 图片格式不支持 | 非支持的图片格式 | 返回 `UnsupportedImageFormatError` |
| 图片过大 | 超过大小限制 | 自动压缩或返回 `ImageTooLargeError` |
| 图片数量超限 | 单次请求图片过多 | 返回 `TooManyImagesError` |

### 7.2 异常类定义

```python
class ImageProcessingError(LLMException):
    """图像处理错误基类"""
    pass

class ImageAccessError(ImageProcessingError):
    """图片无法访问"""
    def __init__(self, url: str, reason: str):
        super().__init__(
            message=f"Cannot access image: {url}",
            error_code="IMAGE_ACCESS_ERROR",
            details={"url": url, "reason": reason},
            status_code=400
        )

class UnsupportedImageFormatError(ImageProcessingError):
    """不支持的图片格式"""
    def __init__(self, format: str):
        super().__init__(
            message=f"Unsupported image format: {format}",
            error_code="UNSUPPORTED_IMAGE_FORMAT",
            details={"format": format},
            status_code=400
        )

class ImageTooLargeError(ImageProcessingError):
    """图片过大"""
    def __init__(self, size: int, max_size: int):
        super().__init__(
            message=f"Image too large: {size} bytes (max: {max_size})",
            error_code="IMAGE_TOO_LARGE",
            details={"size": size, "max_size": max_size},
            status_code=400
        )
```

---

## 8. 配置项

### 8.1 环境变量

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `DASHSCOPE_API_KEY` | 阿里云百炼 API Key | - |
| `QWEN_BASE_URL` | API 基础 URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `QWEN_TIMEOUT` | 请求超时（秒） | `120` |
| `QWEN_MAX_IMAGE_SIZE` | 最大图片大小（字节） | `10485760` (10MB) |

### 8.2 模型默认参数

```python
QWEN_VL_DEFAULT_PARAMS = {
    "temperature": 0.7,
    "max_tokens": 4096,
    "top_p": 1.0,
}

QWEN_VL_THINKING_PARAMS = {
    "enable_thinking": True,
    "thinking_budget": 4096,
}
```

---

## 9. 测试用例

### 9.1 单元测试清单

- [ ] `test_basic_vision_url`: URL 图片基础理解
- [ ] `test_basic_vision_base64`: Base64 图片基础理解
- [ ] `test_multi_image`: 多图理解
- [ ] `test_vision_with_thinking`: 视觉 + 思考模式
- [ ] `test_vision_with_tools`: 视觉 + 工具调用
- [ ] `test_vision_streaming`: 视觉流式响应
- [ ] `test_image_preprocessing`: 图片预处理
- [ ] `test_image_format_detection`: 图片格式检测
- [ ] `test_image_resize`: 图片缩放
- [ ] `test_error_invalid_url`: 无效 URL 错误处理
- [ ] `test_error_unsupported_format`: 不支持格式错误处理
- [ ] `test_error_image_too_large`: 图片过大错误处理

### 9.2 集成测试

测试脚本位置：`backend/tests/qwen_test/test_qwen_vision.py`

---

## 10. 注意事项

1. **图片大小限制**：不同模型对图片大小有不同限制，建议预处理时统一压缩
2. **URL 可访问性**：确保图片 URL 可被模型服务访问，内网 URL 可能无法使用
3. **Base64 编码**：使用 Base64 时需包含正确的 MIME 类型前缀
4. **多图顺序**：多图输入时，图片顺序会影响模型理解
5. **思考模式 Token**：视觉 + 思考模式会消耗更多 Token，注意设置 `thinking_budget`
6. **流式响应**：视觉模型的流式响应可能较慢，建议设置较长超时
7. **工具调用**：视觉 + 工具调用时，模型需要先理解图片再决定是否调用工具

---

## 11. 各提供商差异对比

| 特性 | Qwen VL | OpenAI GPT-4V | Anthropic Claude 3 | Gemini Pro Vision |
|------|---------|---------------|--------------------|--------------------|
| API 格式 | OpenAI 兼容 | 原生 | 独立格式 | OpenAI 兼容 |
| 多图支持 | ✅ | ✅ | ✅ | ✅ |
| Base64 支持 | ✅ | ✅ | ✅ | ✅ |
| 思考模式 | ✅ (qwen3-vl) | ❌ | ✅ | ❌ |
| 工具调用 | ✅ | ✅ | ✅ | ✅ |
| 视频理解 | ✅ (部分模型) | ❌ | ❌ | ✅ |
| 最大图片数 | 10+ | 20 | 20 | 16 |

---

## 12. 参考资料

- [阿里云百炼 Qwen VL 文档](https://help.aliyun.com/zh/model-studio/developer-reference/qwen-vl-api)
- [OpenAI Vision API](https://platform.openai.com/docs/guides/vision)
- [Anthropic Claude Vision](https://docs.anthropic.com/claude/docs/vision)
- 项目适配器基类：`backend/app/core/adapters/base.py`
