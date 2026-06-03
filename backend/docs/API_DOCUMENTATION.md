# MyAI Studio API 接口文档

## 📋 文档说明

本文档详细描述了 MyAI Studio 后端 API 的所有接口，包括请求参数、响应格式、数据类型、示例等，用于前后端接口对接和联调。

**基础信息**
- **Base URL**: `http://localhost:8000`
- **API 版本**: v1
- **API 前缀**: `/api/v1`
- **认证方式**: Header 中传递 `X-User-ID` (UUID 格式)
- **内容类型**: `application/json` (除文件上传外)
- **字符编码**: UTF-8

**通用响应格式**

成功响应：
```json
{
  // 具体数据根据接口而定
}
```

错误响应：
```json
{
  "error": "ERROR_CODE",
  "message": "错误描述",
  "details": {} // 可选，详细错误信息
}
```

**通用 HTTP 状态码**
- `200 OK` - 请求成功
- `201 Created` - 资源创建成功
- `400 Bad Request` - 请求参数错误
- `401 Unauthorized` - 未授权
- `403 Forbidden` - 禁止访问
- `404 Not Found` - 资源不存在
- `422 Unprocessable Entity` - 请求验证失败
- `500 Internal Server Error` - 服务器内部错误

---

## 📑 目录

1. [健康检查](#1-健康检查)
2. [会话管理](#2-会话管理)
3. [聊天接口](#3-聊天接口)
4. [模型配置](#4-模型配置)
5. [文件管理](#5-文件管理)
6. [批处理任务](#6-批处理任务)
7. [数据模型](#7-数据模型)

---

## 1. 健康检查

### 1.1 根端点

获取应用基本信息。

**请求**
```
GET /
```

**响应**
```json
{
  "name": "MyAI Studio",
  "version": "1.0.0",
  "environment": "development",
  "docs_url": "/docs",
  "redoc_url": "/redoc",
  "health_url": "/api/v1/health"
}
```

### 1.2 健康检查（根级别）

快速健康检查。

**请求**
```
GET /health
```

**响应**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-22T07:42:00.885038+00:00"
}
```

### 1.3 API v1 健康检查

API v1 版本的健康检查。

**请求**
```
GET /api/v1/health
```

**响应**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "development",
  "timestamp": "2026-01-22T07:42:11.928323+00:00"
}
```

### 1.4 就绪检查

检查应用是否就绪（包含数据库、Redis 等检查）。

**请求**
```
GET /api/v1/health/ready
```

**响应**
```json
{
  "status": "ready",
  "version": "1.0.0",
  "environment": "development",
  "checks": {
    "database": "not_configured",
    "redis": "not_configured"
  },
  "timestamp": "2026-01-22T07:42:21.337350+00:00"
}
```

---

## 2. 会话管理

### 2.1 创建会话

创建新的聊天会话。

**请求**
```
POST /api/v1/sessions
```

**Headers**
```
Content-Type: application/json
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**请求体**
```json
{
  "title": "新对话",
  "description": "关于 Python 编程的讨论"
}
```

**字段说明**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 否 | 会话标题，默认 "New Chat"，最大 255 字符 |
| description | string | 否 | 会话描述 |

**响应** (200 OK)
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "title": "新对话",
  "description": "关于 Python 编程的讨论",
  "is_archived": false,
  "created_at": "2026-01-22T08:00:00Z",
  "updated_at": "2026-01-22T08:00:00Z",
  "message_count": 0
}
```

### 2.2 列出会话

获取用户的会话列表（支持分页）。

**请求**
```
GET /api/v1/sessions?page=1&page_size=20&include_archived=false
```

**Headers**
```
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**查询参数**
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| page | integer | 否 | 1 | 页码，最小值 1 |
| page_size | integer | 否 | 20 | 每页数量，范围 1-100 |
| include_archived | boolean | 否 | false | 是否包含已归档会话 |

**响应** (200 OK)
```json
{
  "items": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "title": "新对话",
      "description": "关于 Python 编程的讨论",
      "is_archived": false,
      "created_at": "2026-01-22T08:00:00Z",
      "updated_at": "2026-01-22T08:00:00Z",
      "message_count": 5
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

### 2.3 获取会话详情

获取会话详细信息（包含消息列表）。

**请求**
```
GET /api/v1/sessions/{session_id}
```

**Headers**
```
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**路径参数**
| 参数 | 类型 | 说明 |
|------|------|------|
| session_id | UUID | 会话 ID |

**响应** (200 OK)
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "title": "新对话",
  "description": "关于 Python 编程的讨论",
  "is_archived": false,
  "created_at": "2026-01-22T08:00:00Z",
  "updated_at": "2026-01-22T08:00:00Z",
  "message_count": 2,
  "messages": [
    {
      "id": "msg-001",
      "role": "user",
      "content": "你好",
      "thinking_content": null,
      "tokens_used": null,
      "model_used": null,
      "provider_used": null,
      "tool_calls": null,
      "created_at": "2026-01-22T08:01:00Z",
      "attachments": null
    },
    {
      "id": "msg-002",
      "role": "assistant",
      "content": "你好！有什么我可以帮助你的吗？",
      "thinking_content": null,
      "tokens_used": 15,
      "model_used": "deepseek-chat",
      "provider_used": "deepseek",
      "tool_calls": null,
      "created_at": "2026-01-22T08:01:02Z",
      "attachments": null
    }
  ],
  "config": {
    "id": "config-001",
    "model_id": "deepseek-chat",
    "provider": "deepseek",
    "temperature": 70,
    "max_tokens": 2000,
    "top_p": 95,
    "system_prompt": "你是一个有帮助的助手"
  }
}
```

### 2.4 更新会话

更新会话信息。

**请求**
```
PATCH /api/v1/sessions/{session_id}
```

**Headers**
```
Content-Type: application/json
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**请求体**
```json
{
  "title": "Python 编程讨论",
  "description": "更新后的描述",
  "is_archived": false
}
```

**字段说明**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 否 | 会话标题，最大 255 字符 |
| description | string | 否 | 会话描述 |
| is_archived | boolean | 否 | 是否归档 |

**响应** (200 OK)
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "title": "Python 编程讨论",
  "description": "更新后的描述",
  "is_archived": false,
  "created_at": "2026-01-22T08:00:00Z",
  "updated_at": "2026-01-22T08:05:00Z",
  "message_count": 5
}
```

### 2.5 删除会话

删除指定会话。

**请求**
```
DELETE /api/v1/sessions/{session_id}
```

**Headers**
```
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**响应** (200 OK)
```json
{
  "success": true
}
```

### 2.6 获取会话配置

获取会话的模型配置。

**请求**
```
GET /api/v1/sessions/{session_id}/config
```

**Headers**
```
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**响应** (200 OK)
```json
{
  "id": "config-001",
  "model_id": "deepseek-chat",
  "provider": "deepseek",
  "temperature": 70,
  "max_tokens": 2000,
  "top_p": 95,
  "system_prompt": "你是一个有帮助的助手"
}
```

### 2.7 更新会话配置

更新会话的模型配置。

**请求**
```
PATCH /api/v1/sessions/{session_id}/config
```

**Headers**
```
Content-Type: application/json
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**请求体**
```json
{
  "model_id": "qwen-plus",
  "provider": "qwen",
  "temperature": 80,
  "max_tokens": 4000,
  "top_p": 90,
  "system_prompt": "你是一个专业的 Python 编程助手"
}
```

**字段说明**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | string | 否 | 模型 ID |
| provider | string | 否 | 提供商：openai, anthropic, deepseek, gemini, qwen, openrouter, ollama, local |
| temperature | integer | 否 | 温度参数，范围 0-100 |
| max_tokens | integer | 否 | 最大 token 数 |
| top_p | integer | 否 | Top-p 参数，范围 0-100 |
| system_prompt | string | 否 | 系统提示词 |

**响应** (200 OK)
```json
{
  "id": "config-001",
  "model_id": "qwen-plus",
  "provider": "qwen",
  "temperature": 80,
  "max_tokens": 4000,
  "top_p": 90,
  "system_prompt": "你是一个专业的 Python 编程助手"
}
```

### 2.8 获取会话消息

获取会话的消息历史（支持游标分页）。

**请求**
```
GET /api/v1/sessions/{session_id}/messages?limit=50&before_id=msg-100
```

**Headers**
```
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**查询参数**
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| limit | integer | 否 | 50 | 消息数量限制，范围 1-100 |
| before_id | UUID | 否 | null | 游标分页：获取此 ID 之前的消息 |

**响应** (200 OK)
```json
[
  {
    "id": "msg-001",
    "role": "user",
    "content": "你好",
    "thinking_content": null,
    "tokens_used": null,
    "model_used": null,
    "provider_used": null,
    "tool_calls": null,
    "created_at": "2026-01-22T08:01:00Z",
    "attachments": null
  },
  {
    "id": "msg-002",
    "role": "assistant",
    "content": "你好！有什么我可以帮助你的吗？",
    "thinking_content": null,
    "tokens_used": 15,
    "model_used": "deepseek-chat",
    "provider_used": "deepseek",
    "tool_calls": null,
    "created_at": "2026-01-22T08:01:02Z",
    "attachments": null
  }
]
```

---

## 3. 聊天接口

### 3.1 流式聊天 (SSE)

发送消息并接收流式响应（Server-Sent Events）。

**请求**
```
POST /api/v1/chat/stream
```

**Headers**
```
Content-Type: application/json
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**请求体**
```json
{
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "message": "请解释一下 Python 的装饰器",
  "file_ids": ["file-001", "file-002"],
  "stream": true
}
```

**字段说明**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session_id | UUID | 是 | 会话 ID |
| message | string | 是 | 用户消息内容 |
| file_ids | array[UUID] | 否 | 附件文件 ID 列表 |
| stream | boolean | 否 | 是否流式响应，默认 true |

**响应** (200 OK, text/event-stream)

SSE 流式响应，每个事件格式：
```
data: {"type": "content", "content": "Python"}

data: {"type": "content", "content": " 的装饰器"}

data: {"type": "content", "content": "是一种"}

data: {"type": "done"}
```

**事件类型**
| 类型 | 说明 | 数据字段 |
|------|------|----------|
| content | 内容片段 | content: string |
| thinking | 思考过程 | content: string |
| tool_call | 工具调用 | tool_call: object |
| done | 完成 | - |
| error | 错误 | error: string, message: string |

### 3.2 非流式聊天

发送消息并接收完整响应。

**请求**
```
POST /api/v1/chat/complete
```

**Headers**
```
Content-Type: application/json
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**请求体**
```json
{
  "session_id": "123e4567-e29b-12d3-a456-426614174000",
  "message": "请解释一下 Python 的装饰器",
  "file_ids": null,
  "stream": false
}
```

**响应** (200 OK)
```json
{
  "id": "msg-003",
  "role": "assistant",
  "content": "Python 的装饰器是一种特殊的函数...",
  "thinking_content": null,
  "tokens_used": 150,
  "model_used": "deepseek-chat",
  "provider_used": "deepseek",
  "tool_calls": null,
  "created_at": "2026-01-22T08:10:00Z",
  "attachments": null
}
```

### 3.3 获取聊天历史

获取指定会话的聊天历史。

**请求**
```
GET /api/v1/chat/history/{session_id}?limit=50
```

**Headers**
```
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**查询参数**
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| limit | integer | 否 | 50 | 消息数量限制，范围 1-100 |

**响应** (200 OK)
```json
[
  {
    "id": "msg-001",
    "role": "user",
    "content": "你好",
    "created_at": "2026-01-22T08:01:00Z"
  },
  {
    "id": "msg-002",
    "role": "assistant",
    "content": "你好！有什么我可以帮助你的吗？",
    "tokens_used": 15,
    "model_used": "deepseek-chat",
    "created_at": "2026-01-22T08:01:02Z"
  }
]
```

---
## 4. 模型配置

### 4.1 获取适配器类型

获取所有支持的适配器类型和模型信息。

**请求**
```
GET /api/v1/models/adapter-types
```

**响应** (200 OK)
```json
{
  "official": {
    "description": "官方直连适配器（按供应商划分）",
    "providers": [
      {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "requires_api_key": true,
        "models": [
          {
            "id": "deepseek-chat",
            "name": "DeepSeek Chat",
            "supports_vision": false,
            "supports_tools": true,
            "supports_reasoning": true
          },
          {
            "id": "deepseek-reasoner",
            "name": "DeepSeek Reasoner",
            "supports_vision": false,
            "supports_tools": true,
            "supports_reasoning": true
          }
        ]
      },
      {
        "id": "qwen",
        "name": "Qwen (阿里云百炼)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "requires_api_key": true,
        "models": [
          {
            "id": "qwen-plus",
            "name": "Qwen Plus",
            "supports_vision": false,
            "supports_tools": true,
            "supports_reasoning": false
          },
          {
            "id": "qwen3-plus",
            "name": "Qwen3 Plus",
            "supports_vision": false,
            "supports_tools": true,
            "supports_reasoning": true
          },
          {
            "id": "qwen-vl-plus",
            "name": "Qwen VL Plus",
            "supports_vision": true,
            "supports_tools": true,
            "supports_reasoning": false
          }
        ]
      }
    ]
  },
  "openrouter": {
    "description": "OpenRouter 统一网关（按模态划分）",
    "base_url": "https://openrouter.ai/api/v1",
    "requires_api_key": true,
    "text_models": [
      "google/gemini-3-pro-preview",
      "anthropic/claude-3.5-sonnet",
      "meta-llama/llama-3.3-70b-instruct"
    ],
    "vision_models": [
      "google/gemini-3-pro-image-preview",
      "google/gemini-3-pro-preview",
      "openai/gpt-4o"
    ],
    "audio_models": []
  },
  "ollama": {
    "description": "本地 Ollama 部署",
    "base_url": "http://localhost:11434",
    "requires_api_key": false,
    "note": "需自行安装和管理模型，通过 ollama pull 下载"
  },
  "vllm": {
    "description": "高性能本地推理引擎",
    "base_url": "http://localhost:8000/v1",
    "requires_api_key": false,
    "note": "兼容 OpenAI API，需自行部署 vLLM 服务"
  }
}
```

---

## 5. 文件管理

### 5.1 上传文件

上传文件（图片、视频、音频、文档）。

**请求**
```
POST /api/v1/files/upload
```

**Headers**
```
Content-Type: multipart/form-data
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**请求体** (multipart/form-data)
```
file: <binary data>
```

**响应** (200 OK)
```json
{
  "id": "file-001",
  "name": "example.png",
  "type": "image",
  "mime_type": "image/png",
  "size": 102400,
  "url": "/api/v1/files/file-001/download",
  "created_at": "2026-01-22T08:15:00Z"
}
```

**字段说明**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 文件 ID |
| name | string | 文件名 |
| type | string | 文件类型：image, video, audio, document |
| mime_type | string | MIME 类型 |
| size | integer | 文件大小（字节） |
| url | string | 下载 URL |
| created_at | datetime | 创建时间 |

### 5.2 列出文件

获取用户的文件列表。

**请求**
```
GET /api/v1/files?file_type=image
```

**Headers**
```
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**查询参数**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file_type | string | 否 | 文件类型筛选：image, video, audio, document |

**响应** (200 OK)
```json
[
  {
    "id": "file-001",
    "name": "example.png",
    "type": "image",
    "mime_type": "image/png",
    "size": 102400,
    "url": "/api/v1/files/file-001/download",
    "created_at": "2026-01-22T08:15:00Z",
    "file_metadata": {
      "width": 1920,
      "height": 1080
    }
  }
]
```

### 5.3 获取文件信息

获取指定文件的详细信息。

**请求**
```
GET /api/v1/files/{file_id}
```

**Headers**
```
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**响应** (200 OK)
```json
{
  "id": "file-001",
  "name": "example.png",
  "type": "image",
  "mime_type": "image/png",
  "size": 102400,
  "url": "/api/v1/files/file-001/download",
  "created_at": "2026-01-22T08:15:00Z",
  "file_metadata": {
    "width": 1920,
    "height": 1080
  }
}
```

### 5.4 下载文件

下载文件内容。

**请求**
```
GET /api/v1/files/{file_id}/download
```

**Headers**
```
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**响应** (200 OK)
- Content-Type: 根据文件类型
- Content-Disposition: attachment; filename="example.png"
- 响应体：文件二进制数据

### 5.5 删除文件

删除指定文件。

**请求**
```
DELETE /api/v1/files/{file_id}
```

**Headers**
```
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**响应** (200 OK)
```json
{
  "success": true
}
```

---

## 6. 批处理任务

### 6.1 创建批处理任务

创建批量推理任务。

**请求**
```
POST /api/v1/batch
```

**Headers**
```
Content-Type: application/json
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**请求体**
```json
{
  "name": "批量翻译任务",
  "items": [
    {
      "prompt": "Translate to English: 你好",
      "system_prompt": "You are a translator",
      "metadata": {"index": 1}
    },
    {
      "prompt": "Translate to English: 世界",
      "system_prompt": "You are a translator",
      "metadata": {"index": 2}
    }
  ],
  "model_config_id": "config-001",
  "temperature": 70,
  "max_tokens": 100
}
```

**字段说明**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 任务名称，最大 255 字符 |
| items | array | 是 | 批处理项列表 |
| items[].prompt | string | 是 | 提示词 |
| items[].system_prompt | string | 否 | 系统提示词 |
| items[].metadata | object | 否 | 元数据 |
| model_config_id | UUID | 是 | 模型配置 ID |
| temperature | integer | 否 | 温度参数，范围 0-100 |
| max_tokens | integer | 否 | 最大 token 数 |

**响应** (200 OK)
```json
{
  "id": "batch-001",
  "name": "批量翻译任务",
  "status": "pending",
  "total_items": 2,
  "processed_items": 0,
  "failed_items": 0,
  "progress_percent": 0.0,
  "created_at": "2026-01-22T08:20:00Z",
  "started_at": null,
  "completed_at": null
}
```

### 6.2 列出批处理任务

获取批处理任务列表。

**请求**
```
GET /api/v1/batch?status=running
```

**Headers**
```
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**查询参数**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | string | 否 | 状态筛选：pending, running, completed, failed, cancelled |

**响应** (200 OK)
```json
[
  {
    "id": "batch-001",
    "name": "批量翻译任务",
    "status": "running",
    "total_items": 2,
    "processed_items": 1,
    "failed_items": 0,
    "progress_percent": 50.0,
    "created_at": "2026-01-22T08:20:00Z",
    "started_at": "2026-01-22T08:20:05Z",
    "completed_at": null
  }
]
```

### 6.3 获取批处理任务详情

获取指定批处理任务的详细信息。

**请求**
```
GET /api/v1/batch/{batch_id}
```

**Headers**
```
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**响应** (200 OK)
```json
{
  "id": "batch-001",
  "name": "批量翻译任务",
  "status": "completed",
  "total_items": 2,
  "processed_items": 2,
  "failed_items": 0,
  "progress_percent": 100.0,
  "created_at": "2026-01-22T08:20:00Z",
  "started_at": "2026-01-22T08:20:05Z",
  "completed_at": "2026-01-22T08:20:30Z"
}
```

### 6.4 获取批处理进度

获取批处理任务的实时进度。

**请求**
```
GET /api/v1/batch/{batch_id}/status
```

**Headers**
```
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**响应** (200 OK)
```json
{
  "status": "running",
  "progress": {
    "total": 100,
    "processed": 45,
    "failed": 2,
    "percent": 47.0
  }
}
```

### 6.5 取消批处理任务

取消正在运行的批处理任务。

**请求**
```
POST /api/v1/batch/{batch_id}/cancel
```

**Headers**
```
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**响应** (200 OK)
```json
{
  "id": "batch-001",
  "name": "批量翻译任务",
  "status": "cancelled",
  "total_items": 100,
  "processed_items": 45,
  "failed_items": 2,
  "progress_percent": 47.0,
  "created_at": "2026-01-22T08:20:00Z",
  "started_at": "2026-01-22T08:20:05Z",
  "completed_at": "2026-01-22T08:25:00Z"
}
```

### 6.6 获取批处理项列表

获取批处理任务的所有处理项。

**请求**
```
GET /api/v1/batch/{batch_id}/items?status=completed
```

**Headers**
```
X-User-ID: 550e8400-e29b-41d4-a716-446655440000
```

**查询参数**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | string | 否 | 状态筛选：pending, processing, completed, failed, skipped |

**响应** (200 OK)
```json
[
  {
    "id": "item-001",
    "status": "completed",
    "input_data": {
      "prompt": "Translate to English: 你好",
      "system_prompt": "You are a translator",
      "metadata": {"index": 1}
    },
    "output_data": {
      "content": "Hello",
      "tokens_used": 5
    },
    "error_message": null,
    "retry_count": 0
  },
  {
    "id": "item-002",
    "status": "completed",
    "input_data": {
      "prompt": "Translate to English: 世界",
      "system_prompt": "You are a translator",
      "metadata": {"index": 2}
    },
    "output_data": {
      "content": "World",
      "tokens_used": 4
    },
    "error_message": null,
    "retry_count": 0
  }
]
```

---
## 7. 数据模型

### 7.1 会话相关

#### SessionResponse
```typescript
{
  id: string;              // UUID
  title: string;           // 会话标题
  description: string | null;  // 会话描述
  is_archived: boolean;    // 是否归档
  created_at: string;      // ISO 8601 格式
  updated_at: string;      // ISO 8601 格式
  message_count: number;   // 消息数量
}
```

#### SessionDetailResponse
```typescript
{
  id: string;
  title: string;
  description: string | null;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  message_count: number;
  messages: MessageResponse[];  // 消息列表
  config: SessionConfigResponse | null;  // 会话配置
}
```

#### SessionConfigResponse
```typescript
{
  id: string;              // UUID
  model_id: string;        // 模型 ID
  provider: string;        // 提供商
  temperature: number;     // 温度参数 0-100
  max_tokens: number | null;  // 最大 token 数
  top_p: number | null;    // Top-p 参数 0-100
  system_prompt: string | null;  // 系统提示词
}
```

### 7.2 消息相关

#### MessageResponse
```typescript
{
  id: string;              // UUID
  role: "user" | "assistant" | "system";  // 角色
  content: string;         // 消息内容
  thinking_content: string | null;  // 思考过程（推理模型）
  tokens_used: number | null;  // 使用的 token 数
  model_used: string | null;  // 使用的模型
  provider_used: string | null;  // 使用的提供商
  tool_calls: object[] | null;  // 工具调用记录
  created_at: string;      // ISO 8601 格式
  attachments: FileResponse[] | null;  // 附件列表
}
```

### 7.3 文件相关

#### FileResponse
```typescript
{
  id: string;              // UUID
  name: string;            // 文件名
  type: "image" | "video" | "audio" | "document";  // 文件类型
  mime_type: string;       // MIME 类型
  size: number;            // 文件大小（字节）
  url: string | null;      // 下载 URL
  created_at: string;      // ISO 8601 格式
  file_metadata: object | null;  // 文件元数据
}
```

### 7.4 批处理相关

#### BatchJobResponse
```typescript
{
  id: string;              // UUID
  name: string;            // 任务名称
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  total_items: number;     // 总项数
  processed_items: number; // 已处理项数
  failed_items: number;    // 失败项数
  progress_percent: number;  // 进度百分比
  created_at: string;      // ISO 8601 格式
  started_at: string | null;  // 开始时间
  completed_at: string | null;  // 完成时间
}
```

#### BatchItemResponse
```typescript
{
  id: string;              // UUID
  status: "pending" | "processing" | "completed" | "failed" | "skipped";
  input_data: object;      // 输入数据
  output_data: object | null;  // 输出数据
  error_message: string | null;  // 错误信息
  retry_count: number;     // 重试次数
}
```

### 7.5 分页响应

#### PaginatedResponse<T>
```typescript
{
  items: T[];              // 数据项列表
  total: number;           // 总数
  page: number;            // 当前页码
  page_size: number;       // 每页数量
  total_pages: number;     // 总页数
}
```

---

## 8. 错误码

### 8.1 通用错误码

| 错误码 | HTTP 状态码 | 说明 |
|--------|-------------|------|
| VALIDATION_ERROR | 400 | 请求参数验证失败 |
| UNAUTHORIZED | 401 | 未授权 |
| FORBIDDEN | 403 | 禁止访问 |
| NOT_FOUND | 404 | 资源不存在 |
| INTERNAL_SERVER_ERROR | 500 | 服务器内部错误 |

### 8.2 业务错误码

| 错误码 | HTTP 状态码 | 说明 |
|--------|-------------|------|
| SESSION_NOT_FOUND | 404 | 会话不存在 |
| MODEL_CONFIG_NOT_FOUND | 404 | 模型配置不存在 |
| FILE_NOT_FOUND | 404 | 文件不存在 |
| BATCH_JOB_NOT_FOUND | 404 | 批处理任务不存在 |
| INVALID_FILE_TYPE | 400 | 不支持的文件类型 |
| FILE_TOO_LARGE | 400 | 文件过大 |
| LLM_API_ERROR | 500 | LLM API 调用失败 |
| RATE_LIMIT_EXCEEDED | 429 | 请求频率超限 |

---

## 9. 使用示例

### 9.1 JavaScript/TypeScript (Fetch API)

#### 创建会话并发送消息

```typescript
// 1. 创建会话
const createSession = async () => {
  const response = await fetch('http://localhost:8000/api/v1/sessions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': '550e8400-e29b-41d4-a716-446655440000'
    },
    body: JSON.stringify({
      title: '新对话',
      description: 'Python 编程讨论'
    })
  });
  
  const session = await response.json();
  return session.id;
};

// 2. 发送消息（流式）
const sendMessage = async (sessionId: string, message: string) => {
  const response = await fetch('http://localhost:8000/api/v1/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': '550e8400-e29b-41d4-a716-446655440000'
    },
    body: JSON.stringify({
      session_id: sessionId,
      message: message,
      stream: true
    })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        
        if (data.type === 'content') {
          console.log(data.content);
        } else if (data.type === 'done') {
          console.log('完成');
        } else if (data.type === 'error') {
          console.error('错误:', data.message);
        }
      }
    }
  }
};

// 使用示例
const main = async () => {
  const sessionId = await createSession();
  await sendMessage(sessionId, '请解释一下 Python 的装饰器');
};
```

#### 上传文件

```typescript
const uploadFile = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('http://localhost:8000/api/v1/files/upload', {
    method: 'POST',
    headers: {
      'X-User-ID': '550e8400-e29b-41d4-a716-446655440000'
    },
    body: formData
  });

  const fileInfo = await response.json();
  return fileInfo;
};
```

### 9.2 Python (requests)

#### 创建会话并发送消息

```python
import requests
import json

BASE_URL = "http://localhost:8000"
USER_ID = "550e8400-e29b-41d4-a716-446655440000"

# 1. 创建会话
def create_session():
    response = requests.post(
        f"{BASE_URL}/api/v1/sessions",
        headers={
            "Content-Type": "application/json",
            "X-User-ID": USER_ID
        },
        json={
            "title": "新对话",
            "description": "Python 编程讨论"
        }
    )
    session = response.json()
    return session["id"]

# 2. 发送消息（流式）
def send_message(session_id, message):
    response = requests.post(
        f"{BASE_URL}/api/v1/chat/stream",
        headers={
            "Content-Type": "application/json",
            "X-User-ID": USER_ID
        },
        json={
            "session_id": session_id,
            "message": message,
            "stream": True
        },
        stream=True
    )

    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                data = json.loads(line[6:])
                
                if data['type'] == 'content':
                    print(data['content'], end='', flush=True)
                elif data['type'] == 'done':
                    print('\n完成')
                elif data['type'] == 'error':
                    print(f'\n错误: {data["message"]}')

# 使用示例
if __name__ == "__main__":
    session_id = create_session()
    send_message(session_id, "请解释一下 Python 的装饰器")
```

#### 上传文件

```python
def upload_file(file_path):
    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(
            f"{BASE_URL}/api/v1/files/upload",
            headers={"X-User-ID": USER_ID},
            files=files
        )
    
    file_info = response.json()
    return file_info
```

---

## 10. 注意事项

### 10.1 认证

- 当前版本使用简化的认证方式，通过 `X-User-ID` Header 传递用户 ID
- 生产环境应使用 JWT 或其他安全的认证方式
- 所有需要认证的接口都必须传递 `X-User-ID` Header

### 10.2 请求限制

- 文件上传大小限制：根据配置而定（默认建议 10MB）
- 批处理任务项数限制：建议不超过 1000 项
- 消息内容长度：建议不超过 10000 字符

### 10.3 SSE 流式响应

- 使用 `text/event-stream` 内容类型
- 每个事件以 `data: ` 开头，后跟 JSON 数据
- 事件之间用空行分隔
- 连接保持活跃，直到收到 `done` 或 `error` 事件

### 10.4 时间格式

- 所有时间字段使用 ISO 8601 格式
- 示例：`2026-01-22T08:00:00Z`
- 时区：UTC

### 10.5 UUID 格式

- 所有 ID 字段使用 UUID v4 格式
- 示例：`550e8400-e29b-41d4-a716-446655440000`

---

## 11. 更新日志

### v1.0.0 (2026-01-22)

- ✅ 实现所有 31 个 API 端点
- ✅ 支持四类适配器架构（OFFICIAL, OPENROUTER, OLLAMA, VLLM）
- ✅ 支持 SSE 流式响应
- ✅ 支持文件上传和管理
- ✅ 支持批处理任务
- ✅ 完整的错误处理和异常管理

---

## 12. 联系方式

如有问题或建议，请通过以下方式联系：

- GitHub Issues: https://github.com/your-org/my-ai-studio/issues
- API 文档: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

**文档版本**: 1.0.0  
**最后更新**: 2026-01-22  
**维护者**: MyAI Studio Team
