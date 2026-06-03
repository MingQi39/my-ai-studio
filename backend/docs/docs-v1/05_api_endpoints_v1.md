# Phase 5: API 接口层

> **目标**: 通过 HTTP 暴露服务，实现完整的 RESTful API 和 SSE 流式端点。
> **预计工时**: 3-4 天
> **前置依赖**: Phase 4 完成

---

## 1. 阶段概述

本阶段聚焦于 `api/v1/` 目录的实现，包括 FastAPI 路由定义、SSE 流式响应、文件上传、中间件配置和异常处理。完成后，前端应能通过 HTTP API 与后端完整交互。

---

## 2. 任务清单

### 2.1 API 路由注册

- [ ] 更新 `backend/app/api/__init__.py`
  - [ ] 创建 API 路由聚合

- [ ] 更新 `backend/app/api/v1/__init__.py`
  - [ ] 创建 v1 版本路由器
  - [ ] 注册所有子路由

- [ ] 更新 `backend/app/main.py`
  - [ ] 挂载 v1 路由到 `/api/v1`
  - [ ] 配置全局异常处理器

### 2.2 中间件配置

- [ ] 创建 `backend/app/api/middleware.py`

#### 2.2.1 CORS 中间件

- [ ] 配置 `CORSMiddleware`
  - [ ] 从配置读取允许的源
  - [ ] 允许凭证
  - [ ] 允许所有方法
  - [ ] 允许所有头部

#### 2.2.2 请求日志中间件

- [ ] 实现 `RequestLoggingMiddleware`
  - [ ] 记录请求方法、路径、耗时
  - [ ] 生成请求 ID
  - [ ] 添加请求 ID 到响应头
  - [ ] 记录响应状态码

#### 2.2.3 异常处理中间件

- [ ] 实现全局异常处理器
  ```python
  @app.exception_handler(LLMException)
  async def llm_exception_handler(request: Request, exc: LLMException):
      return JSONResponse(
          status_code=exc.status_code,
          content={
              "error": exc.error_code,
              "message": exc.message,
              "details": exc.details,
              "timestamp": exc.timestamp.isoformat()
          }
      )
  ```

- [ ] 实现 `RequestValidationError` 处理器
  - [ ] 格式化验证错误
  - [ ] 返回 400 状态码

- [ ] 实现通用异常处理器
  - [ ] 捕获未处理异常
  - [ ] 记录错误日志
  - [ ] 返回 500 状态码

### 2.3 依赖注入更新

- [ ] 更新 `backend/app/dependencies.py`

- [ ] 实现 `get_current_user` 依赖 (简化版)
  ```python
  async def get_current_user(
      x_user_id: UUID = Header(..., alias="X-User-ID")
  ) -> UUID:
      # 简化版：直接从 Header 获取用户 ID
      # 生产环境应使用 JWT 验证
      return x_user_id
  ```

- [ ] 实现 `get_session_service` 依赖
- [ ] 实现 `get_model_service` 依赖
- [ ] 实现 `get_chat_service` 依赖
- [ ] 实现 `get_file_service` 依赖
- [ ] 实现 `get_batch_service` 依赖

### 2.4 健康检查端点

- [ ] 更新 `backend/app/api/v1/health.py`

- [ ] 实现 `GET /api/v1/health`
  ```python
  @router.get("/health")
  async def health_check():
      return {
          "status": "healthy",
          "version": settings.APP_VERSION,
          "environment": settings.ENVIRONMENT
      }
  ```

- [ ] 实现 `GET /api/v1/health/ready`
  - [ ] 检查数据库连接
  - [ ] 检查 Redis 连接 (如果启用)
  - [ ] 返回就绪状态

### 2.5 会话端点

- [ ] 创建 `backend/app/api/v1/sessions.py`

#### 2.5.1 会话 CRUD

- [ ] 实现 `POST /api/v1/sessions`
  - [ ] 请求体: `SessionCreate`
  - [ ] 响应: `SessionResponse`
  - [ ] 创建新会话

- [ ] 实现 `GET /api/v1/sessions`
  - [ ] 查询参数: `page`, `page_size`, `include_archived`
  - [ ] 响应: `PaginatedResponse[SessionResponse]`
  - [ ] 列出用户会话

- [ ] 实现 `GET /api/v1/sessions/{session_id}`
  - [ ] 路径参数: `session_id`
  - [ ] 响应: `SessionDetailResponse`
  - [ ] 获取会话详情 (含消息)

- [ ] 实现 `PATCH /api/v1/sessions/{session_id}`
  - [ ] 路径参数: `session_id`
  - [ ] 请求体: `SessionUpdate`
  - [ ] 响应: `SessionResponse`
  - [ ] 更新会话信息

- [ ] 实现 `DELETE /api/v1/sessions/{session_id}`
  - [ ] 路径参数: `session_id`
  - [ ] 响应: `{"success": true}`
  - [ ] 删除会话

#### 2.5.2 会话配置

- [ ] 实现 `GET /api/v1/sessions/{session_id}/config`
  - [ ] 响应: `SessionConfigResponse`
  - [ ] 获取会话配置

- [ ] 实现 `PATCH /api/v1/sessions/{session_id}/config`
  - [ ] 请求体: `SessionConfigUpdate`
  - [ ] 响应: `SessionConfigResponse`
  - [ ] 更新会话配置

#### 2.5.3 会话消息

- [ ] 实现 `GET /api/v1/sessions/{session_id}/messages`
  - [ ] 查询参数: `limit`, `before_id`
  - [ ] 响应: `list[MessageResponse]`
  - [ ] 获取会话消息历史

### 2.6 聊天端点

- [ ] 创建 `backend/app/api/v1/chat.py`

#### 2.6.1 流式聊天 (SSE)

- [ ] 实现 `POST /api/v1/chat/stream`
  - [ ] 请求体: `ChatRequest`
  - [ ] 响应: `StreamingResponse` (text/event-stream)
  - [ ] SSE 流式返回

- [ ] 实现 SSE 生成器
  ```python
  async def generate_sse(
      chat_service: ChatService,
      session_id: UUID,
      user_id: UUID,
      request: ChatRequest
  ) -> AsyncIterator[str]:
      try:
          async for chunk in chat_service.chat(session_id, user_id, request):
              yield f"data: {json.dumps(chunk)}\n\n"
          yield f"data: {json.dumps({'type': 'done'})}\n\n"
      except LLMException as e:
          yield f"data: {json.dumps({'type': 'error', 'error': e.message})}\n\n"
  ```

- [ ] 配置 SSE 响应头
  ```python
  return StreamingResponse(
      generate_sse(...),
      media_type="text/event-stream",
      headers={
          "Cache-Control": "no-cache",
          "Connection": "keep-alive",
          "X-Accel-Buffering": "no"  # 禁用 nginx 缓冲
      }
  )
  ```

#### 2.6.2 非流式聊天

- [ ] 实现 `POST /api/v1/chat/complete`
  - [ ] 请求体: `ChatRequest` (stream=False)
  - [ ] 响应: `MessageResponse`
  - [ ] 直接返回完整响应

#### 2.6.3 聊天历史

- [ ] 实现 `GET /api/v1/chat/history/{session_id}`
  - [ ] 查询参数: `limit`
  - [ ] 响应: `list[MessageResponse]`
  - [ ] 获取聊天历史

### 2.7 模型配置端点

- [ ] 创建 `backend/app/api/v1/models.py`

#### 2.7.1 模型配置 CRUD

- [ ] 实现 `POST /api/v1/models`
  - [ ] 请求体: `ModelConfigCreate`
  - [ ] 响应: `ModelConfigResponse`
  - [ ] 创建模型配置

- [ ] 实现 `GET /api/v1/models`
  - [ ] 查询参数: `adapter_type` (OFFICIAL/OPENROUTER/OLLAMA/VLLM), `provider` (仅 OFFICIAL 类型有效)
  - [ ] 响应: `list[ModelConfigResponse]`
  - [ ] 列出模型配置

- [ ] 实现 `GET /api/v1/models/{config_id}`
  - [ ] 响应: `ModelConfigResponse`
  - [ ] 获取模型配置详情

- [ ] 实现 `PATCH /api/v1/models/{config_id}`
  - [ ] 请求体: `ModelConfigUpdate`
  - [ ] 响应: `ModelConfigResponse`
  - [ ] 更新模型配置

- [ ] 实现 `DELETE /api/v1/models/{config_id}`
  - [ ] 响应: `{"success": true}`
  - [ ] 删除模型配置

**注意事项**：
- `ModelConfigCreate` 必须包含 `adapter_type` 字段（OFFICIAL/OPENROUTER/OLLAMA/VLLM）
- 当 `adapter_type` 为 OFFICIAL 时，必须提供 `provider` 字段（deepseek/qwen/openai 等）
- 当 `adapter_type` 为 OPENROUTER/OLLAMA/VLLM 时，`provider` 字段应为 null
- API Key 加密存储，响应中不返回明文
- 创建配置时会验证 `adapter_type` 和 `provider` 的组合有效性

#### 2.7.2 模型验证

- [ ] 实现 `POST /api/v1/models/{config_id}/validate`
  - [ ] 响应: `{"valid": bool, "error": str | None}`
  - [ ] 验证模型配置凭证

- [ ] 实现 `GET /api/v1/models/{config_id}/available`
  - [ ] 响应: `list[ModelInfo]`
  - [ ] 列出可用模型

#### 2.7.3 适配器类型与 Provider 信息

- [ ] 实现 `GET /api/v1/models/adapter-types`
  - [ ] 响应: 支持的适配器类型及配置信息
  ```python
  return {
      "official": {
          "description": "官方直连适配器（按供应商划分）",
          "providers": [
              {
                  "id": "deepseek",
                  "name": "DeepSeek",
                  "base_url": "https://api.deepseek.com",
                  "requires_api_key": True,
                  "models": [
                      {
                          "id": "deepseek-chat",
                          "name": "DeepSeek Chat",
                          "supports_vision": False,
                          "supports_tools": True,
                          "supports_reasoning": True
                      },
                      {
                          "id": "deepseek-reasoner",
                          "name": "DeepSeek Reasoner",
                          "supports_vision": False,
                          "supports_tools": True,
                          "supports_reasoning": True
                      }
                  ]
              },
              {
                  "id": "qwen",
                  "name": "Qwen (阿里云百炼)",
                  "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                  "requires_api_key": True,
                  "models": [
                      {
                          "id": "qwen-plus",
                          "name": "Qwen Plus",
                          "supports_vision": False,
                          "supports_tools": True,
                          "supports_reasoning": False
                      },
                      {
                          "id": "qwen3-plus",
                          "name": "Qwen3 Plus",
                          "supports_vision": False,
                          "supports_tools": True,
                          "supports_reasoning": True
                      },
                      {
                          "id": "qwen-vl-plus",
                          "name": "Qwen VL Plus",
                          "supports_vision": True,
                          "supports_tools": True,
                          "supports_reasoning": False
                      }
                  ]
              }
          ]
      },
      "openrouter": {
          "description": "OpenRouter 统一网关（按模态划分）",
          "base_url": "https://openrouter.ai/api/v1",
          "requires_api_key": True,
          "text_models": [
              "google/gemini-2.0-flash-001",
              "anthropic/claude-3.5-sonnet",
              "meta-llama/llama-3.3-70b-instruct"
          ],
          "vision_models": [
              "google/gemini-2.5-pro-preview",
              "openai/gpt-4o",
              "anthropic/claude-3.5-sonnet"
          ],
          "audio_models": []
      },
      "ollama": {
          "description": "本地 Ollama 部署",
          "base_url": "http://localhost:11434",
          "requires_api_key": False,
          "note": "需自行安装和管理模型，通过 ollama pull 下载"
      },
      "vllm": {
          "description": "高性能本地推理引擎",
          "base_url": "http://localhost:8000/v1",
          "requires_api_key": False,
          "note": "兼容 OpenAI API，需自行部署 vLLM 服务"
      }
  }
  ```

- [ ] 或者实现 `GET /api/v1/models/providers` (保持原端点名称)
  - [ ] 响应结构同上，体现四类适配器架构
  - [ ] 从 `config/providers.yaml` 读取配置
  - [ ] 动态返回可用的适配器类型和模型列表


### 2.8 文件端点

- [ ] 创建 `backend/app/api/v1/files.py`

#### 2.8.1 文件上传

- [ ] 实现 `POST /api/v1/files/upload`
  - [ ] 请求: `multipart/form-data`
  - [ ] 参数: `file: UploadFile`
  - [ ] 响应: `FileUploadResponse`
  - [ ] 上传文件

- [ ] 配置文件大小限制
  ```python
  @router.post("/upload")
  async def upload_file(
      file: UploadFile = File(..., max_length=settings.MAX_UPLOAD_SIZE)
  ):
      ...
  ```

#### 2.8.2 文件管理

- [ ] 实现 `GET /api/v1/files`
  - [ ] 查询参数: `type`
  - [ ] 响应: `list[FileResponse]`
  - [ ] 列出用户文件

- [ ] 实现 `GET /api/v1/files/{file_id}`
  - [ ] 响应: `FileResponse`
  - [ ] 获取文件信息

- [ ] 实现 `GET /api/v1/files/{file_id}/download`
  - [ ] 响应: `FileResponse` (binary)
  - [ ] 下载文件内容

- [ ] 实现 `DELETE /api/v1/files/{file_id}`
  - [ ] 响应: `{"success": true}`
  - [ ] 删除文件

### 2.9 批处理端点

- [ ] 创建 `backend/app/api/v1/batch.py`

#### 2.9.1 批处理任务管理

- [ ] 实现 `POST /api/v1/batch`
  - [ ] 请求体: `BatchJobCreate`
  - [ ] 响应: `BatchJobResponse`
  - [ ] 创建批处理任务

- [ ] 实现 `GET /api/v1/batch`
  - [ ] 查询参数: `status`
  - [ ] 响应: `list[BatchJobResponse]`
  - [ ] 列出批处理任务

- [ ] 实现 `GET /api/v1/batch/{batch_id}`
  - [ ] 响应: `BatchJobResponse`
  - [ ] 获取批处理任务详情

- [ ] 实现 `GET /api/v1/batch/{batch_id}/status`
  - [ ] 响应: 进度信息
  ```python
  return {
      "status": job.status,
      "progress": {
          "total": job.total_items,
          "processed": job.processed_items,
          "failed": job.failed_items,
          "percent": (job.processed_items + job.failed_items) / job.total_items * 100
      }
  }
  ```

- [ ] 实现 `POST /api/v1/batch/{batch_id}/cancel`
  - [ ] 响应: `BatchJobResponse`
  - [ ] 取消批处理任务

#### 2.9.2 批处理项查询

- [ ] 实现 `GET /api/v1/batch/{batch_id}/items`
  - [ ] 查询参数: `status`
  - [ ] 响应: `list[BatchItemResponse]`
  - [ ] 获取批处理项列表

### 2.10 API 文档配置

- [ ] 更新 `backend/app/main.py`

- [ ] 配置 OpenAPI 元数据
  ```python
  app = FastAPI(
      title="MyAI Studio API",
      description="通用大模型接入平台后端服务",
      version=settings.APP_VERSION,
      docs_url="/docs",
      redoc_url="/redoc",
      openapi_url="/openapi.json"
  )
  ```

- [ ] 配置 API 标签
  ```python
  tags_metadata = [
      {"name": "health", "description": "健康检查"},
      {"name": "sessions", "description": "会话管理"},
      {"name": "chat", "description": "聊天接口"},
      {"name": "models", "description": "模型配置"},
      {"name": "files", "description": "文件管理"},
      {"name": "batch", "description": "批处理任务"},
  ]
  ```

- [ ] 为每个路由添加标签
  ```python
  @router.get("/sessions", tags=["sessions"])
  ```

### 2.11 响应模型配置

- [ ] 为所有端点配置响应模型
  ```python
  @router.get(
      "/sessions/{session_id}",
      response_model=SessionDetailResponse,
      responses={
          404: {"description": "Session not found"},
          403: {"description": "Access denied"}
      }
  )
  ```

---

## 3. 验收标准

### 3.1 功能验收

- [ ] 所有端点可通过 Swagger UI 测试
- [ ] SSE 流式响应正常工作
- [ ] 文件上传正常工作
- [ ] CORS 配置正确 (前端可跨域访问)
- [ ] 异常正确转换为 HTTP 错误响应
- [ ] 请求日志正确记录

### 3.2 API 规范验收

- [ ] 所有端点遵循 RESTful 规范
- [ ] 响应格式统一
- [ ] 错误响应格式统一
- [ ] OpenAPI 文档完整

### 3.3 测试验收

- [ ] 创建 `backend/tests/test_api_sessions.py`
- [ ] 创建 `backend/tests/test_api_chat.py`
- [ ] 创建 `backend/tests/test_api_models.py`
- [ ] 创建 `backend/tests/test_api_files.py`
- [ ] 创建 `backend/tests/test_api_batch.py`
- [ ] 所有 API 测试通过
- [ ] 使用 `httpx.AsyncClient` 进行测试

---

## 4. 目录结构预览

完成本阶段后，`api/` 目录结构应如下：

```
backend/app/api/
├── __init__.py
├── middleware.py        # 中间件配置
└── v1/
    ├── __init__.py      # v1 路由聚合
    ├── health.py        # 健康检查
    ├── sessions.py      # 会话端点
    ├── chat.py          # 聊天端点
    ├── models.py        # 模型配置端点
    ├── files.py         # 文件端点
    └── batch.py         # 批处理端点
```

---

## 5. API 端点汇总

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/health` | 健康检查 |
| GET | `/api/v1/health/ready` | 就绪检查 |
| POST | `/api/v1/sessions` | 创建会话 |
| GET | `/api/v1/sessions` | 列出会话 |
| GET | `/api/v1/sessions/{id}` | 获取会话详情 |
| PATCH | `/api/v1/sessions/{id}` | 更新会话 |
| DELETE | `/api/v1/sessions/{id}` | 删除会话 |
| GET | `/api/v1/sessions/{id}/config` | 获取会话配置 |
| PATCH | `/api/v1/sessions/{id}/config` | 更新会话配置 |
| GET | `/api/v1/sessions/{id}/messages` | 获取会话消息 |
| POST | `/api/v1/chat/stream` | 流式聊天 (SSE) |
| POST | `/api/v1/chat/complete` | 非流式聊天 |
| GET | `/api/v1/chat/history/{id}` | 获取聊天历史 |
| POST | `/api/v1/models` | 创建模型配置 |
| GET | `/api/v1/models` | 列出模型配置 |
| GET | `/api/v1/models/{id}` | 获取模型配置 |
| PATCH | `/api/v1/models/{id}` | 更新模型配置 |
| DELETE | `/api/v1/models/{id}` | 删除模型配置 |
| POST | `/api/v1/models/{id}/validate` | 验证模型配置 |
| GET | `/api/v1/models/{id}/available` | 列出可用模型 |
| GET | `/api/v1/models/adapter-types` | 列出支持的适配器类型及 Provider 信息 |
| POST | `/api/v1/files/upload` | 上传文件 |
| GET | `/api/v1/files` | 列出文件 |
| GET | `/api/v1/files/{id}` | 获取文件信息 |
| GET | `/api/v1/files/{id}/download` | 下载文件 |
| DELETE | `/api/v1/files/{id}` | 删除文件 |
| POST | `/api/v1/batch` | 创建批处理任务 |
| GET | `/api/v1/batch` | 列出批处理任务 |
| GET | `/api/v1/batch/{id}` | 获取批处理任务 |
| GET | `/api/v1/batch/{id}/status` | 获取批处理进度 |
| POST | `/api/v1/batch/{id}/cancel` | 取消批处理任务 |
| GET | `/api/v1/batch/{id}/items` | 获取批处理项 |

---

## 6. 编码规范与最佳实践

### 6.1 代码风格

#### 6.1.1 关键原则
- 编写简洁、技术性的代码，并附上准确的 Python 示例
- 尽可能使用函数式、声明式编程；避免使用类（除非必要，如 Pydantic 模型）
- 优先选择迭代和模块化，而非代码重复
- 使用带有辅助动词的描述性变量名（例如，`is_active`、`has_permission`）
- 对于目录和文件，使用小写加下划线（例如，`routers/user_routes.py`）
- 对于路由和实用函数，优先使用命名导出
- 使用接收对象、返回对象（RORO）模式

#### 6.1.2 Python/FastAPI 规范
- 对于纯函数使用 `def`，对于异步操作使用 `async def`
- 对所有函数签名使用类型提示
- 在输入验证时，优先使用 Pydantic 模型而非原始字典
- 文件结构：导出的路由器、子路由、工具、静态内容、类型（模型、模式）
- 在条件语句中避免不必要的花括号
- 对于简单的条件语句，使用简洁的一行语法（例如，`if condition: do_something()`）

**示例**：
```python
# 路由定义示例
from fastapi import APIRouter, Depends, HTTPException
from app.models.schemas import SessionCreate, SessionResponse
from app.services import SessionService
from app.dependencies import get_session_service, get_current_user

router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.post("", response_model=SessionResponse)
async def create_session(
    data: SessionCreate,
    user_id: UUID = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service)
) -> SessionResponse:
    """创建新会话"""
    session = await session_service.create_session(user_id, data)
    return SessionResponse.from_orm(session)
```

### 6.2 错误处理与验证

#### 6.2.1 错误处理原则
- 优先考虑错误处理和边界情况
- 在函数开头处理错误和边界情况
- 对于错误条件使用提前返回，以避免深度嵌套的 if 语句
- 将正常执行路径放在函数末尾，以提高可读性
- 避免不必要的 else 语句；使用 if-return 模式代替
- 使用保护子句尽早处理前置条件和无效状态
- 实现恰当的错误日志记录和用户友好的错误消息
- 使用自定义错误类型或错误工厂以实现一致的错误处理

**示例**：
```python
@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: UUID,
    user_id: UUID = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service)
) -> SessionDetailResponse:
    """获取会话详情"""
    # 提前返回处理错误情况
    session = await session_service.get_session(session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # 正常执行路径
    return SessionDetailResponse.from_orm(session)
```

#### 6.2.2 异常处理策略
- 对于预期错误使用 `HTTPException`，并将其建模为特定的 HTTP 响应
- 使用中间件处理意外错误、日志记录和错误监控
- 使用 Pydantic 的 `BaseModel` 进行一致的输入/输出验证和响应模式定义
- 将 Core 层的 `LLMException` 转换为合适的 HTTP 状态码

### 6.3 FastAPI 特定指南

#### 6.3.1 路由定义
- 使用函数组件（普通函数）和 Pydantic 模型进行输入验证和响应模式定义
- 使用声明式路由定义，并明确返回类型注释
- 对于同步操作使用 `def`，对于异步操作使用 `async def`
- 为每个路由添加清晰的文档字符串

#### 6.3.2 依赖注入
- 依靠 FastAPI 的依赖注入系统来管理状态和共享资源
- 使用 `Depends()` 注入服务实例、数据库会话、当前用户等
- 避免在路由函数中直接实例化服务

**示例**：
```python
# dependencies.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services import SessionService, ModelService

async def get_session_service(
    db: AsyncSession = Depends(get_db)
) -> SessionService:
    return SessionService(db)

async def get_model_service(
    db: AsyncSession = Depends(get_db)
) -> ModelService:
    return ModelService(db)
```

#### 6.3.3 生命周期管理
- 尽量减少使用 `@app.on_event("startup")` 和 `@app.on_event("shutdown")`
- 更推荐使用生命周期上下文管理器来管理启动和关闭事件

**示例**：
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    await init_database()
    yield
    # 关闭时执行
    await close_database()

app = FastAPI(lifespan=lifespan)
```

### 6.4 性能优化

#### 6.4.1 异步操作
- 尽量减少阻塞式 I/O 操作
- 对所有数据库调用和外部 API 请求使用异步操作
- 在路由中限制阻塞操作：
  - 优先采用异步和非阻塞流程
  - 对数据库和外部 API 操作使用专门的异步函数
  - 清晰地构建路由和依赖关系，以优化可读性和可维护性

#### 6.4.2 缓存策略
- 使用 Redis 或内存存储等工具为静态数据和频繁访问的数据实现缓存
- 利用 Pydantic 对数据序列化和反序列化进行优化
- 对大型数据集和大量 API 响应采用延迟加载技术

#### 6.4.3 性能监控
- 优先考虑 API 性能指标（响应时间、延迟、吞吐量）
- 使用中间件进行日志记录、错误监控和性能优化
- 通过为 I/O 密集型任务使用异步函数、缓存策略和延迟加载来优化性能

### 6.5 安全注意事项

1. **SSE 响应不要缓冲** - 设置正确的响应头
2. **文件上传要限制大小** - 防止 DoS 攻击
3. **CORS 要配置正确** - 确保前端可访问
4. **异常要统一处理** - 不要泄露内部错误
5. **请求 ID 要传递** - 便于日志追踪
6. **响应模型要完整** - 便于前端类型推断
7. **API 版本要明确** - 便于后续升级
8. **适配器类型验证** - 创建模型配置时验证 adapter_type 和 provider 的组合有效性
9. **API Key 安全** - 响应中永远不返回明文 API Key

### 6.6 依赖项

本项目使用以下核心依赖：
- **FastAPI** - Web 框架
- **Pydantic v2** - 数据验证和序列化
- **SQLAlchemy 2.0** - ORM 和数据库操作
- **asyncpg** - PostgreSQL 异步驱动
- **httpx** - 异步 HTTP 客户端（用于 LLM API 调用）

### 6.7 关键惯例

1. 依靠 FastAPI 的依赖注入系统来管理状态和共享资源
2. 优先考虑 API 性能指标（响应时间、延迟、吞吐量）
3. 在路由中限制阻塞操作：
   - 优先采用异步和非阻塞流程
   - 对数据库和外部 API 操作使用专门的异步函数
   - 清晰地构建路由和依赖关系，以优化可读性和可维护性
4. 有关数据模型、路径操作和中间件的最佳实践，请参阅 [FastAPI 官方文档](https://fastapi.tiangolo.com/)

---

## 7. 下一阶段预告

完成本阶段后，进入 **Phase 6: 异步任务与部署**，将实现：
- Celery 配置和任务定义
- Redis 连接
- 批处理任务执行
- Docker 部署配置
