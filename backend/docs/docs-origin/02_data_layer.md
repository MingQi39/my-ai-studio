# Phase 2: 数据层与模型定义

> **目标**: 确立数据契约 (Data Contract)。严禁在此阶段编写业务逻辑，只定义表结构和类型。
> **预计工时**: 2-3 天
> **前置依赖**: Phase 1 完成

---

## 1. 阶段概述

本阶段聚焦于数据层的设计与实现，包括 SQLAlchemy ORM 模型、Pydantic 数据传输对象 (DTO/Schema) 和 Alembic 数据库迁移配置。完成后，应能通过迁移脚本创建所有数据库表。

---

## 2. 任务清单

### 2.1 数据库连接配置

- [ ] 创建 `backend/app/db/database.py`
  - [ ] 配置 SQLAlchemy 异步引擎 (AsyncEngine)
  - [ ] 配置异步会话工厂 (async_sessionmaker)
  - [ ] 创建 `Base` 声明基类
  - [ ] 实现 `get_db()` 异步依赖函数
  - [ ] 实现数据库初始化函数 `init_db()`
  - [ ] 实现数据库关闭函数 `close_db()`

- [ ] 更新 `backend/app/dependencies.py`
  - [ ] 导入并注册 `get_db` 依赖

- [ ] 更新 `backend/app/main.py`
  - [ ] 在 lifespan 中调用数据库初始化/关闭

### 2.2 SQLAlchemy 模型定义

- [ ] 创建 `backend/app/models/database.py` (ORM 模型)

#### 2.2.1 基础模型混入类

- [ ] 定义 `TimestampMixin` 混入类
  - [ ] `created_at`: DateTime, 自动设置创建时间
  - [ ] `updated_at`: DateTime, 自动更新修改时间

- [ ] 定义 `UUIDMixin` 混入类
  - [ ] `id`: UUID, 主键, 自动生成

#### 2.2.2 用户模型 (User)

- [ ] 定义 `User` 模型
  - [ ] `id`: UUID, PK
  - [ ] `email`: String(255), unique, indexed
  - [ ] `username`: String(100), unique, indexed
  - [ ] `hashed_password`: String(255)
  - [ ] `is_active`: Boolean, default=True
  - [ ] `created_at`: DateTime
  - [ ] `updated_at`: DateTime
  - [ ] 关系: sessions, model_configs, files, batch_jobs

#### 2.2.3 会话模型 (Session)

- [ ] 定义 `Session` 模型
  - [ ] `id`: UUID, PK
  - [ ] `user_id`: UUID, FK(users.id), indexed
  - [ ] `title`: String(255), default="New Chat"
  - [ ] `description`: Text, nullable
  - [ ] `is_archived`: Boolean, default=False
  - [ ] `created_at`: DateTime, indexed
  - [ ] `updated_at`: DateTime
  - [ ] 关系: user, messages, config

#### 2.2.4 消息模型 (Message)

- [ ] 定义 `MessageRole` 枚举
  - [ ] `user`
  - [ ] `assistant`
  - [ ] `system`

- [ ] 定义 `Message` 模型
  - [ ] `id`: UUID, PK
  - [ ] `session_id`: UUID, FK(sessions.id), indexed
  - [ ] `role`: Enum(MessageRole), indexed
  - [ ] `content`: Text
  - [ ] `thinking_content`: Text, nullable (推理链)
  - [ ] `tokens_used`: Integer, nullable
  - [ ] `model_used`: String(100), nullable
  - [ ] `provider_used`: String(50), nullable
  - [ ] `tool_calls`: JSON, nullable
  - [ ] `created_at`: DateTime, indexed
  - [ ] 关系: session, attachments, tool_executions

#### 2.2.5 会话配置模型 (SessionConfig)

- [ ] 定义 `LLMProvider` 枚举
  - [ ] `openai`
  - [ ] `anthropic`
  - [ ] `deepseek`
  - [ ] `gemini`
  - [ ] `qwen`
  - [ ] `openrouter`
  - [ ] `ollama`
  - [ ] `local`

- [ ] 定义 `SessionConfig` 模型
  - [ ] `id`: UUID, PK
  - [ ] `session_id`: UUID, FK(sessions.id), unique
  - [ ] `model_id`: String(100)
  - [ ] `provider`: Enum(LLMProvider)
  - [ ] `temperature`: Integer (0-100)
  - [ ] `max_tokens`: Integer, nullable
  - [ ] `top_p`: Integer (0-100), nullable
  - [ ] `system_prompt`: Text, nullable
  - [ ] 关系: session

#### 2.2.6 模型配置模型 (ModelConfig)

- [ ] 定义 `ModelConfig` 模型
  - [ ] `id`: UUID, PK
  - [ ] `user_id`: UUID, FK(users.id), indexed
  - [ ] `provider`: Enum(LLMProvider), indexed
  - [ ] `name`: String(100)
  - [ ] `api_key`: Text (加密存储)
  - [ ] `base_url`: String(500)
  - [ ] `model_id`: String(100)
  - [ ] `is_default`: Boolean, default=False
  - [ ] `is_active`: Boolean, default=True
  - [ ] `created_at`: DateTime
  - [ ] `updated_at`: DateTime
  - [ ] 关系: user

#### 2.2.7 文件模型 (File)

- [ ] 定义 `FileType` 枚举
  - [ ] `image`
  - [ ] `video`
  - [ ] `audio`
  - [ ] `document`

- [ ] 定义 `File` 模型
  - [ ] `id`: UUID, PK
  - [ ] `user_id`: UUID, FK(users.id), indexed
  - [ ] `name`: String(255)
  - [ ] `type`: Enum(FileType)
  - [ ] `mime_type`: String(100)
  - [ ] `size`: BigInteger (bytes)
  - [ ] `storage_path`: String(500)
  - [ ] `url`: String(500), nullable
  - [ ] `metadata`: JSON, nullable
  - [ ] `created_at`: DateTime, indexed
  - [ ] 关系: user, message_attachments

#### 2.2.8 消息附件关联模型 (MessageAttachment)

- [ ] 定义 `MessageAttachment` 模型
  - [ ] `id`: UUID, PK
  - [ ] `message_id`: UUID, FK(messages.id), indexed
  - [ ] `file_id`: UUID, FK(files.id), indexed
  - [ ] `position`: Integer (排序)
  - [ ] 关系: message, file

#### 2.2.9 批处理任务模型 (BatchJob)

- [ ] 定义 `BatchJobStatus` 枚举
  - [ ] `pending`
  - [ ] `running`
  - [ ] `completed`
  - [ ] `failed`
  - [ ] `cancelled`

- [ ] 定义 `BatchJob` 模型
  - [ ] `id`: UUID, PK
  - [ ] `user_id`: UUID, FK(users.id), indexed
  - [ ] `name`: String(255)
  - [ ] `status`: Enum(BatchJobStatus)
  - [ ] `total_items`: Integer
  - [ ] `processed_items`: Integer, default=0
  - [ ] `failed_items`: Integer, default=0
  - [ ] `created_at`: DateTime, indexed
  - [ ] `started_at`: DateTime, nullable
  - [ ] `completed_at`: DateTime, nullable
  - [ ] 关系: user, items

#### 2.2.10 批处理项模型 (BatchItem)

- [ ] 定义 `BatchItemStatus` 枚举
  - [ ] `pending`
  - [ ] `processing`
  - [ ] `completed`
  - [ ] `failed`
  - [ ] `skipped`

- [ ] 定义 `BatchItem` 模型
  - [ ] `id`: UUID, PK
  - [ ] `batch_job_id`: UUID, FK(batch_jobs.id), indexed
  - [ ] `input_data`: JSON
  - [ ] `output_data`: JSON, nullable
  - [ ] `status`: Enum(BatchItemStatus)
  - [ ] `error_message`: Text, nullable
  - [ ] `retry_count`: Integer, default=0
  - [ ] `created_at`: DateTime
  - [ ] `started_at`: DateTime, nullable
  - [ ] `completed_at`: DateTime, nullable
  - [ ] 关系: batch_job

#### 2.2.11 工具执行日志模型 (ToolExecution)

- [ ] 定义 `ToolType` 枚举
  - [ ] `code`
  - [ ] `search`
  - [ ] `function`
  - [ ] `structured`

- [ ] 定义 `ToolExecutionStatus` 枚举
  - [ ] `pending`
  - [ ] `running`
  - [ ] `completed`
  - [ ] `failed`

- [ ] 定义 `ToolExecution` 模型
  - [ ] `id`: UUID, PK
  - [ ] `message_id`: UUID, FK(messages.id), indexed
  - [ ] `tool_name`: String(100)
  - [ ] `tool_type`: Enum(ToolType)
  - [ ] `input_params`: JSON
  - [ ] `output`: Text, nullable
  - [ ] `status`: Enum(ToolExecutionStatus)
  - [ ] `error_message`: Text, nullable
  - [ ] `execution_time_ms`: Integer, nullable
  - [ ] `created_at`: DateTime
  - [ ] 关系: message

### 2.3 Pydantic Schemas (DTOs)

- [ ] 创建 `backend/app/models/schemas.py`

#### 2.3.1 通用 Schema

- [ ] 定义 `BaseSchema` 基类
  - [ ] 配置 `from_attributes = True`
  - [ ] 配置 JSON 序列化器

- [ ] 定义 `PaginationParams` 分页参数
  - [ ] `page`: int, default=1, ge=1
  - [ ] `page_size`: int, default=20, ge=1, le=100

- [ ] 定义 `PaginatedResponse[T]` 泛型响应
  - [ ] `items`: list[T]
  - [ ] `total`: int
  - [ ] `page`: int
  - [ ] `page_size`: int
  - [ ] `total_pages`: int

#### 2.3.2 用户 Schema

- [ ] 定义 `UserCreate`
  - [ ] `email`: EmailStr
  - [ ] `username`: str, min_length=3, max_length=100
  - [ ] `password`: str, min_length=8

- [ ] 定义 `UserUpdate`
  - [ ] `username`: str | None
  - [ ] `password`: str | None

- [ ] 定义 `UserResponse`
  - [ ] `id`: UUID
  - [ ] `email`: str
  - [ ] `username`: str
  - [ ] `is_active`: bool
  - [ ] `created_at`: datetime

#### 2.3.3 会话 Schema

- [ ] 定义 `SessionCreate`
  - [ ] `title`: str | None = "New Chat"
  - [ ] `description`: str | None

- [ ] 定义 `SessionUpdate`
  - [ ] `title`: str | None
  - [ ] `description`: str | None
  - [ ] `is_archived`: bool | None

- [ ] 定义 `SessionResponse`
  - [ ] `id`: UUID
  - [ ] `title`: str
  - [ ] `description`: str | None
  - [ ] `is_archived`: bool
  - [ ] `created_at`: datetime
  - [ ] `updated_at`: datetime
  - [ ] `message_count`: int (计算字段)

- [ ] 定义 `SessionDetailResponse` (含消息列表)
  - [ ] 继承 `SessionResponse`
  - [ ] `messages`: list[MessageResponse]
  - [ ] `config`: SessionConfigResponse | None

#### 2.3.4 消息 Schema

- [ ] 定义 `MessageCreate`
  - [ ] `content`: str
  - [ ] `role`: MessageRole = MessageRole.user
  - [ ] `file_ids`: list[UUID] | None

- [ ] 定义 `MessageResponse`
  - [ ] `id`: UUID
  - [ ] `role`: MessageRole
  - [ ] `content`: str
  - [ ] `thinking_content`: str | None
  - [ ] `tokens_used`: int | None
  - [ ] `model_used`: str | None
  - [ ] `provider_used`: str | None
  - [ ] `tool_calls`: list[dict] | None
  - [ ] `created_at`: datetime
  - [ ] `attachments`: list[FileResponse] | None

#### 2.3.5 会话配置 Schema

- [ ] 定义 `SessionConfigCreate`
  - [ ] `model_id`: str
  - [ ] `provider`: LLMProvider
  - [ ] `temperature`: int = 70, ge=0, le=100
  - [ ] `max_tokens`: int | None
  - [ ] `top_p`: int | None, ge=0, le=100
  - [ ] `system_prompt`: str | None

- [ ] 定义 `SessionConfigUpdate`
  - [ ] 所有字段可选

- [ ] 定义 `SessionConfigResponse`
  - [ ] `id`: UUID
  - [ ] `model_id`: str
  - [ ] `provider`: LLMProvider
  - [ ] `temperature`: int
  - [ ] `max_tokens`: int | None
  - [ ] `top_p`: int | None
  - [ ] `system_prompt`: str | None

#### 2.3.6 模型配置 Schema

- [ ] 定义 `ModelConfigCreate`
  - [ ] `provider`: LLMProvider
  - [ ] `name`: str
  - [ ] `api_key`: str
  - [ ] `base_url`: str
  - [ ] `model_id`: str
  - [ ] `is_default`: bool = False

- [ ] 定义 `ModelConfigUpdate`
  - [ ] 所有字段可选 (api_key 更新时需重新加密)

- [ ] 定义 `ModelConfigResponse`
  - [ ] `id`: UUID
  - [ ] `provider`: LLMProvider
  - [ ] `name`: str
  - [ ] `base_url`: str
  - [ ] `model_id`: str
  - [ ] `is_default`: bool
  - [ ] `is_active`: bool
  - [ ] `created_at`: datetime
  - [ ] **注意**: 不返回 `api_key`

#### 2.3.7 文件 Schema

- [ ] 定义 `FileUploadResponse`
  - [ ] `id`: UUID
  - [ ] `name`: str
  - [ ] `type`: FileType
  - [ ] `mime_type`: str
  - [ ] `size`: int
  - [ ] `url`: str | None
  - [ ] `created_at`: datetime

- [ ] 定义 `FileResponse`
  - [ ] 继承 `FileUploadResponse`
  - [ ] `metadata`: dict | None

#### 2.3.8 批处理 Schema

- [ ] 定义 `BatchJobCreate`
  - [ ] `name`: str
  - [ ] `items`: list[BatchItemInput]
  - [ ] `model_config_id`: UUID
  - [ ] `temperature`: int | None
  - [ ] `max_tokens`: int | None

- [ ] 定义 `BatchItemInput`
  - [ ] `prompt`: str
  - [ ] `system_prompt`: str | None
  - [ ] `metadata`: dict | None

- [ ] 定义 `BatchJobResponse`
  - [ ] `id`: UUID
  - [ ] `name`: str
  - [ ] `status`: BatchJobStatus
  - [ ] `total_items`: int
  - [ ] `processed_items`: int
  - [ ] `failed_items`: int
  - [ ] `progress_percent`: float (计算字段)
  - [ ] `created_at`: datetime
  - [ ] `started_at`: datetime | None
  - [ ] `completed_at`: datetime | None

- [ ] 定义 `BatchItemResponse`
  - [ ] `id`: UUID
  - [ ] `status`: BatchItemStatus
  - [ ] `input_data`: dict
  - [ ] `output_data`: dict | None
  - [ ] `error_message`: str | None
  - [ ] `retry_count`: int

#### 2.3.9 聊天请求 Schema

- [ ] 定义 `ChatRequest`
  - [ ] `session_id`: UUID
  - [ ] `message`: str
  - [ ] `file_ids`: list[UUID] | None
  - [ ] `stream`: bool = True

- [ ] 定义 `ChatStreamChunk`
  - [ ] `type`: str ("content" | "thinking" | "tool_call" | "done" | "error")
  - [ ] `content`: str | None
  - [ ] `tool_call`: dict | None
  - [ ] `error`: str | None
  - [ ] `usage`: dict | None

#### 2.3.10 工具执行 Schema

- [ ] 定义 `ToolExecutionResponse`
  - [ ] `id`: UUID
  - [ ] `tool_name`: str
  - [ ] `tool_type`: ToolType
  - [ ] `input_params`: dict
  - [ ] `output`: str | None
  - [ ] `status`: ToolExecutionStatus
  - [ ] `error_message`: str | None
  - [ ] `execution_time_ms`: int | None
  - [ ] `created_at`: datetime

### 2.4 Alembic 迁移配置

- [ ] 初始化 Alembic
  ```bash
  cd backend
  alembic init app/db/migrations
  ```

- [ ] 配置 `backend/app/db/migrations/env.py`
  - [ ] 导入所有模型
  - [ ] 配置异步迁移支持
  - [ ] 从 config.py 读取数据库 URL

- [ ] 配置 `backend/alembic.ini`
  - [ ] 设置脚本位置
  - [ ] 配置日志

- [ ] 创建初始迁移脚本
  ```bash
  alembic revision --autogenerate -m "Initial migration: create all tables"
  ```

- [ ] 执行迁移
  ```bash
  alembic upgrade head
  ```

### 2.5 模型导出

- [ ] 更新 `backend/app/models/__init__.py`
  - [ ] 导出所有 ORM 模型
  - [ ] 导出所有枚举类型
  - [ ] 导出所有 Pydantic Schema

---

## 3. 验收标准

### 3.1 功能验收

- [ ] 执行 `alembic upgrade head` 成功创建所有表
- [ ] SQLite 数据库文件生成在指定位置
- [ ] 所有表结构符合设计
- [ ] 外键约束正确建立
- [ ] 索引正确创建

### 3.2 代码质量

- [ ] 所有模型有完整的类型注解
- [ ] 所有 Schema 有字段验证
- [ ] 枚举值命名规范
- [ ] 无循环导入

### 3.3 测试验收

- [ ] 创建 `backend/tests/test_models.py`
- [ ] ORM 模型 CRUD 测试通过
- [ ] Schema 验证测试通过
- [ ] 迁移回滚测试通过 (`alembic downgrade -1`)

---

## 4. 数据库 ER 图

```
┌─────────────┐       ┌─────────────────┐       ┌─────────────┐
│   users     │───────│    sessions     │───────│  messages   │
└─────────────┘  1:N  └─────────────────┘  1:N  └─────────────┘
      │                       │                       │
      │                       │ 1:1                   │ 1:N
      │                       ▼                       ▼
      │               ┌───────────────┐       ┌───────────────┐
      │               │session_configs│       │tool_executions│
      │               └───────────────┘       └───────────────┘
      │
      │ 1:N           ┌─────────────┐
      ├───────────────│model_configs│
      │               └─────────────┘
      │
      │ 1:N           ┌─────────────┐       ┌───────────────────┐
      ├───────────────│   files     │───────│message_attachments│
      │               └─────────────┘  1:N  └───────────────────┘
      │                                              │
      │ 1:N           ┌─────────────┐               │
      └───────────────│ batch_jobs  │               │
                      └─────────────┘               │
                            │                       │
                            │ 1:N                   │
                            ▼                       │
                      ┌─────────────┐               │
                      │ batch_items │               │
                      └─────────────┘               │
                                                    │
                      ┌─────────────┐               │
                      │  messages   │◄──────────────┘
                      └─────────────┘
```

---

## 5. 注意事项

1. **严禁编写业务逻辑** - 本阶段只定义数据结构
2. **UUID 使用 uuid4** - 确保全局唯一
3. **时间戳使用 UTC** - 统一时区处理
4. **API Key 必须加密存储** - 使用 Fernet 对称加密
5. **JSON 字段使用 SQLAlchemy JSON 类型** - SQLite 支持
6. **枚举值使用小写字符串** - 便于 API 序列化
7. **Schema 字段验证要严格** - 前端数据不可信

---

## 6. 下一阶段预告

完成本阶段后，进入 **Phase 3: 核心逻辑与适配器**，将实现：
- LLM 适配器基类和具体实现
- 自定义异常层级
- 重试机制和熔断器
- API Key 加密工具
