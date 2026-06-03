# Phase 4: 业务服务层

> **目标**: 将 Core 层的适配器与 Data 层的数据模型连接起来，实现具体的业务流程。
> **预计工时**: 3-4 天
> **前置依赖**: Phase 2 + Phase 3 完成

---

## 1. 阶段概述

本阶段聚焦于 `services/` 目录的实现，包括 ChatService、SessionService、ModelService、FileService 和 BatchService。服务层负责协调 Core 层和 Data 层，实现完整的业务逻辑。

---

## 2. 任务清单

### 2.1 服务基类

- [ ] 创建 `backend/app/services/base.py`

- [ ] 定义 `BaseService` 基类
  ```python
  class BaseService:
      def __init__(self, db: AsyncSession):
          self.db = db
          self.logger = get_logger(self.__class__.__name__)
  ```

### 2.2 会话服务 (SessionService)

- [ ] 创建 `backend/app/services/session_service.py`

#### 2.2.1 会话 CRUD

- [ ] 实现 `create_session(user_id: UUID, data: SessionCreate) -> Session`
  - [ ] 创建会话记录
  - [ ] 创建默认会话配置
  - [ ] 返回完整会话对象

- [ ] 实现 `get_session(session_id: UUID, user_id: UUID) -> Session | None`
  - [ ] 验证会话归属
  - [ ] 加载关联的消息和配置

- [ ] 实现 `list_sessions(user_id: UUID, params: PaginationParams, include_archived: bool = False) -> PaginatedResponse[Session]`
  - [ ] 分页查询
  - [ ] 按创建时间倒序
  - [ ] 可选包含已归档会话

- [ ] 实现 `update_session(session_id: UUID, user_id: UUID, data: SessionUpdate) -> Session`
  - [ ] 验证会话归属
  - [ ] 更新标题/描述/归档状态
  - [ ] 更新 `updated_at`

- [ ] 实现 `delete_session(session_id: UUID, user_id: UUID) -> bool`
  - [ ] 验证会话归属
  - [ ] 级联删除消息和配置
  - [ ] 删除关联文件引用

- [ ] 实现 `archive_session(session_id: UUID, user_id: UUID) -> Session`
  - [ ] 设置 `is_archived = True`

#### 2.2.2 会话配置

- [ ] 实现 `get_session_config(session_id: UUID) -> SessionConfig | None`
  - [ ] 获取会话配置

- [ ] 实现 `update_session_config(session_id: UUID, user_id: UUID, data: SessionConfigUpdate) -> SessionConfig`
  - [ ] 验证会话归属
  - [ ] 更新配置参数
  - [ ] 验证 provider 和 model_id 有效性

#### 2.2.3 消息管理

- [ ] 实现 `add_message(session_id: UUID, data: MessageCreate) -> Message`
  - [ ] 创建消息记录
  - [ ] 关联附件文件
  - [ ] 更新会话 `updated_at`

- [ ] 实现 `get_messages(session_id: UUID, limit: int = 50, before_id: UUID | None = None) -> list[Message]`
  - [ ] 获取会话消息历史
  - [ ] 支持游标分页
  - [ ] 加载附件信息

- [ ] 实现 `get_message(message_id: UUID) -> Message | None`
  - [ ] 获取单条消息
  - [ ] 加载工具执行记录

### 2.3 模型配置服务 (ModelService)

- [ ] 创建 `backend/app/services/model_service.py`

#### 2.3.1 模型配置 CRUD

- [ ] 实现 `create_model_config(user_id: UUID, data: ModelConfigCreate) -> ModelConfig`
  - [ ] 加密 API Key
  - [ ] 验证 provider 有效性
  - [ ] 如果设为默认，取消其他默认配置

- [ ] 实现 `get_model_config(config_id: UUID, user_id: UUID) -> ModelConfig | None`
  - [ ] 验证配置归属
  - [ ] 不返回解密的 API Key

- [ ] 实现 `list_model_configs(user_id: UUID, provider: LLMProvider | None = None) -> list[ModelConfig]`
  - [ ] 按 provider 筛选
  - [ ] 按创建时间排序

- [ ] 实现 `update_model_config(config_id: UUID, user_id: UUID, data: ModelConfigUpdate) -> ModelConfig`
  - [ ] 验证配置归属
  - [ ] 如果更新 API Key，重新加密
  - [ ] 如果设为默认，取消其他默认配置

- [ ] 实现 `delete_model_config(config_id: UUID, user_id: UUID) -> bool`
  - [ ] 验证配置归属
  - [ ] 检查是否有会话正在使用

- [ ] 实现 `get_default_config(user_id: UUID, provider: LLMProvider | None = None) -> ModelConfig | None`
  - [ ] 获取用户默认配置

#### 2.3.2 模型验证

- [ ] 实现 `validate_model_config(config_id: UUID, user_id: UUID) -> dict`
  - [ ] 获取配置并解密 API Key
  - [ ] 创建适配器实例
  - [ ] 调用 `validate_credentials()`
  - [ ] 返回验证结果

- [ ] 实现 `list_available_models(config_id: UUID, user_id: UUID) -> list[ModelInfo]`
  - [ ] 获取配置并解密 API Key
  - [ ] 创建适配器实例
  - [ ] 调用 `list_models()`

#### 2.3.3 适配器获取

- [ ] 实现 `get_adapter(config_id: UUID, user_id: UUID) -> BaseLLMAdapter`
  - [ ] 获取配置并解密 API Key
  - [ ] 使用工厂创建适配器
  - [ ] 返回适配器实例

- [ ] 实现 `get_adapter_for_session(session_id: UUID, user_id: UUID) -> BaseLLMAdapter`
  - [ ] 获取会话配置
  - [ ] 获取对应的模型配置
  - [ ] 创建并返回适配器

### 2.4 聊天服务 (ChatService)

- [ ] 创建 `backend/app/services/chat_service.py`

#### 2.4.1 聊天核心逻辑

- [ ] 实现 `chat(session_id: UUID, user_id: UUID, request: ChatRequest) -> AsyncIterator[ChatStreamChunk]`
  - [ ] 验证会话归属
  - [ ] 获取会话配置
  - [ ] 获取适配器
  - [ ] 构建消息历史
  - [ ] 保存用户消息
  - [ ] 调用适配器 `chat_completion`
  - [ ] 流式返回响应
  - [ ] 保存助手消息
  - [ ] 记录 token 使用

- [ ] 实现 `_build_messages(session_id: UUID, new_message: str, file_ids: list[UUID] | None) -> list[ChatMessage]`
  - [ ] 获取历史消息
  - [ ] 添加系统提示
  - [ ] 处理多模态内容
  - [ ] 构建消息列表

- [ ] 实现 `_process_files(file_ids: list[UUID]) -> list[dict]`
  - [ ] 获取文件信息
  - [ ] 读取文件内容
  - [ ] 转换为 base64
  - [ ] 构建多模态内容块

#### 2.4.2 流式响应处理

- [ ] 实现 `_stream_response(adapter: BaseLLMAdapter, messages: list, config: SessionConfig) -> AsyncIterator[ChatStreamChunk]`
  - [ ] 调用适配器流式接口
  - [ ] 聚合内容块
  - [ ] 分离 thinking 内容
  - [ ] 处理工具调用
  - [ ] 捕获并转换异常

- [ ] 实现 `_save_assistant_message(session_id: UUID, content: str, thinking: str | None, usage: dict | None, tool_calls: list | None) -> Message`
  - [ ] 创建助手消息
  - [ ] 保存 thinking 内容
  - [ ] 保存 token 使用信息
  - [ ] 保存工具调用记录

#### 2.4.3 工具调用处理

- [ ] 实现 `_handle_tool_calls(message_id: UUID, tool_calls: list[dict]) -> list[ToolExecution]`
  - [ ] 解析工具调用
  - [ ] 创建执行记录
  - [ ] (实际执行在 Phase 6 实现)

#### 2.4.4 非流式聊天

- [ ] 实现 `chat_complete(session_id: UUID, user_id: UUID, request: ChatRequest) -> MessageResponse`
  - [ ] 非流式版本
  - [ ] 直接返回完整响应

### 2.5 文件服务 (FileService)

- [ ] 创建 `backend/app/services/file_service.py`

#### 2.5.1 文件上传

- [ ] 实现 `upload_file(user_id: UUID, file: UploadFile) -> File`
  - [ ] 验证文件类型
  - [ ] 验证文件大小
  - [ ] 生成存储路径
  - [ ] 保存文件到磁盘
  - [ ] 提取文件元数据
  - [ ] 创建数据库记录

- [ ] 实现 `_validate_file(file: UploadFile) -> FileType`
  - [ ] 检查 MIME 类型
  - [ ] 检查文件扩展名
  - [ ] 检查文件大小
  - [ ] 返回文件类型

- [ ] 实现 `_generate_storage_path(user_id: UUID, file_id: UUID, extension: str) -> str`
  - [ ] 生成目录结构: `storage/uploads/{user_id}/{file_id}.{ext}`
  - [ ] 确保目录存在

- [ ] 实现 `_extract_metadata(file_path: str, file_type: FileType) -> dict`
  - [ ] 图片: 宽度、高度、格式
  - [ ] 视频: 时长、分辨率、编码
  - [ ] 音频: 时长、采样率、声道
  - [ ] 文档: 页数 (PDF)

#### 2.5.2 文件读取

- [ ] 实现 `get_file(file_id: UUID, user_id: UUID) -> File | None`
  - [ ] 验证文件归属
  - [ ] 返回文件信息

- [ ] 实现 `get_file_content(file_id: UUID, user_id: UUID) -> bytes`
  - [ ] 验证文件归属
  - [ ] 读取文件内容

- [ ] 实现 `get_file_base64(file_id: UUID, user_id: UUID) -> str`
  - [ ] 获取文件内容
  - [ ] 转换为 base64

- [ ] 实现 `list_files(user_id: UUID, file_type: FileType | None = None) -> list[File]`
  - [ ] 按类型筛选
  - [ ] 按创建时间倒序

#### 2.5.3 文件删除

- [ ] 实现 `delete_file(file_id: UUID, user_id: UUID) -> bool`
  - [ ] 验证文件归属
  - [ ] 检查是否被消息引用
  - [ ] 删除磁盘文件
  - [ ] 删除数据库记录

- [ ] 实现 `cleanup_orphan_files() -> int`
  - [ ] 查找无引用的文件
  - [ ] 删除孤立文件
  - [ ] 返回删除数量

### 2.6 批处理服务 (BatchService)

- [ ] 创建 `backend/app/services/batch_service.py`

#### 2.6.1 批处理任务管理

- [ ] 实现 `create_batch_job(user_id: UUID, data: BatchJobCreate) -> BatchJob`
  - [ ] 创建批处理任务
  - [ ] 创建批处理项
  - [ ] 设置状态为 pending
  - [ ] (实际执行在 Phase 6 通过 Celery 实现)

- [ ] 实现 `get_batch_job(batch_id: UUID, user_id: UUID) -> BatchJob | None`
  - [ ] 验证任务归属
  - [ ] 加载任务项

- [ ] 实现 `list_batch_jobs(user_id: UUID, status: BatchJobStatus | None = None) -> list[BatchJob]`
  - [ ] 按状态筛选
  - [ ] 按创建时间倒序

- [ ] 实现 `cancel_batch_job(batch_id: UUID, user_id: UUID) -> BatchJob`
  - [ ] 验证任务归属
  - [ ] 设置状态为 cancelled
  - [ ] 取消未处理的项

#### 2.6.2 批处理项管理

- [ ] 实现 `get_batch_items(batch_id: UUID, user_id: UUID, status: BatchItemStatus | None = None) -> list[BatchItem]`
  - [ ] 验证任务归属
  - [ ] 按状态筛选

- [ ] 实现 `update_batch_item(item_id: UUID, status: BatchItemStatus, output: dict | None = None, error: str | None = None) -> BatchItem`
  - [ ] 更新项状态
  - [ ] 保存输出或错误
  - [ ] 更新父任务计数

- [ ] 实现 `get_batch_progress(batch_id: UUID, user_id: UUID) -> dict`
  - [ ] 计算进度百分比
  - [ ] 返回统计信息

### 2.7 用户服务 (UserService) - 可选

- [ ] 创建 `backend/app/services/user_service.py`

- [ ] 实现 `create_user(data: UserCreate) -> User`
  - [ ] 验证邮箱唯一
  - [ ] 验证用户名唯一
  - [ ] 哈希密码
  - [ ] 创建用户

- [ ] 实现 `get_user(user_id: UUID) -> User | None`

- [ ] 实现 `get_user_by_email(email: str) -> User | None`

- [ ] 实现 `authenticate_user(email: str, password: str) -> User | None`
  - [ ] 验证密码
  - [ ] 返回用户或 None

### 2.8 服务导出

- [ ] 更新 `backend/app/services/__init__.py`
  - [ ] 导出所有服务类

---

## 3. 验收标准

### 3.1 功能验收

- [ ] SessionService: 会话 CRUD 正常工作
- [ ] SessionService: 消息管理正常工作
- [ ] ModelService: 模型配置 CRUD 正常工作
- [ ] ModelService: API Key 加密存储
- [ ] ModelService: 适配器创建正常
- [ ] ChatService: 流式聊天正常工作
- [ ] ChatService: 消息历史正确构建
- [ ] ChatService: 多模态内容正确处理
- [ ] FileService: 文件上传正常工作
- [ ] FileService: 文件类型验证正确
- [ ] FileService: 元数据提取正确
- [ ] BatchService: 批处理任务创建正常

### 3.2 代码质量

- [ ] 所有服务方法有完整类型注解
- [ ] 所有数据库操作使用事务
- [ ] 错误处理完善
- [ ] 日志记录完整

### 3.3 测试验收

- [ ] 创建 `backend/tests/test_session_service.py`
- [ ] 创建 `backend/tests/test_model_service.py`
- [ ] 创建 `backend/tests/test_chat_service.py`
- [ ] 创建 `backend/tests/test_file_service.py`
- [ ] 创建 `backend/tests/test_batch_service.py`
- [ ] 所有测试通过
- [ ] 测试覆盖率 > 80%

---

## 4. 目录结构预览

完成本阶段后，`services/` 目录结构应如下：

```
backend/app/services/
├── __init__.py
├── base.py              # 服务基类
├── session_service.py   # 会话服务
├── model_service.py     # 模型配置服务
├── chat_service.py      # 聊天服务
├── file_service.py      # 文件服务
├── batch_service.py     # 批处理服务
└── user_service.py      # 用户服务 (可选)
```

---

## 5. 注意事项

1. **事务管理** - 多表操作必须使用事务
2. **权限验证** - 所有操作必须验证资源归属
3. **API Key 安全** - 永远不要在日志中输出 API Key
4. **文件安全** - 验证文件类型，防止恶意文件
5. **流式响应** - 正确处理连接中断
6. **错误传播** - 服务层异常应转换为业务异常
7. **性能考虑** - 大量消息历史需要分页加载

---

## 6. 下一阶段预告

完成本阶段后，进入 **Phase 5: API 接口层**，将实现：
- FastAPI 路由定义
- SSE 流式响应端点
- 文件上传端点
- 中间件 (CORS, Auth, Logging)
