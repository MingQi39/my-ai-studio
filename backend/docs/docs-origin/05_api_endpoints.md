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
  - [ ] 查询参数: `provider`
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

#### 2.7.2 模型验证

- [ ] 实现 `POST /api/v1/models/{config_id}/validate`
  - [ ] 响应: `{"valid": bool, "error": str | None}`
  - [ ] 验证模型配置凭证

- [ ] 实现 `GET /api/v1/models/{config_id}/available`
  - [ ] 响应: `list[ModelInfo]`
  - [ ] 列出可用模型

#### 2.7.3 Provider 信息

- [ ] 实现 `GET /api/v1/models/providers`
  - [ ] 响应: 支持的 provider 列表及默认配置
  ```python
  return [
      {
          "id": "openai",
          "name": "OpenAI",
          "base_url": "https://api.openai.com/v1",
          "requires_api_key": True
      },
      ...
  ]
  ```

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
| GET | `/api/v1/models/providers` | 列出支持的 Provider |
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

## 6. 注意事项

1. **SSE 响应不要缓冲** - 设置正确的响应头
2. **文件上传要限制大小** - 防止 DoS 攻击
3. **CORS 要配置正确** - 确保前端可访问
4. **异常要统一处理** - 不要泄露内部错误
5. **请求 ID 要传递** - 便于日志追踪
6. **响应模型要完整** - 便于前端类型推断
7. **API 版本要明确** - 便于后续升级

---

## 7. 下一阶段预告

完成本阶段后，进入 **Phase 6: 异步任务与部署**，将实现：
- Celery 配置和任务定义
- Redis 连接
- 批处理任务执行
- Docker 部署配置
