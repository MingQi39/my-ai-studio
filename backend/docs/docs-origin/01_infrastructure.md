# Phase 1: 基础设施与骨架

> **目标**: 确保应用可以启动（即使是空的），并能正确读取配置。
> **预计工时**: 1-2 天
> **前置依赖**: 无

---

## 1. 阶段概述

本阶段聚焦于搭建项目的基础骨架，包括目录结构、环境配置、日志系统和依赖注入框架。完成后，应用应能成功启动并输出配置信息。

---

## 2. 任务清单

### 2.1 项目目录结构创建

- [ ] 创建 `backend/` 根目录
- [ ] 创建 `backend/app/` 应用主目录
- [ ] 创建 `backend/app/__init__.py`
- [ ] 创建 `backend/app/api/` API 目录
- [ ] 创建 `backend/app/api/__init__.py`
- [ ] 创建 `backend/app/api/v1/` API v1 版本目录
- [ ] 创建 `backend/app/api/v1/__init__.py`
- [ ] 创建 `backend/app/core/` 核心逻辑目录
- [ ] 创建 `backend/app/core/__init__.py`
- [ ] 创建 `backend/app/models/` 数据模型目录
- [ ] 创建 `backend/app/models/__init__.py`
- [ ] 创建 `backend/app/services/` 服务层目录
- [ ] 创建 `backend/app/services/__init__.py`
- [ ] 创建 `backend/app/db/` 数据库目录
- [ ] 创建 `backend/app/db/__init__.py`
- [ ] 创建 `backend/app/tasks/` 异步任务目录
- [ ] 创建 `backend/app/tasks/__init__.py`
- [ ] 创建 `backend/app/utils/` 工具目录
- [ ] 创建 `backend/app/utils/__init__.py`
- [ ] 创建 `backend/tests/` 测试目录
- [ ] 创建 `backend/tests/__init__.py`
- [ ] 创建 `backend/storage/` 文件存储目录
- [ ] 创建 `backend/storage/uploads/` 上传文件目录
- [ ] 创建 `backend/storage/cache/` 缓存目录

### 2.2 依赖管理

- [ ] 创建 `backend/requirements.txt`
  ```
  # Core Framework
  fastapi==0.115.0
  uvicorn[standard]==0.32.0
  pydantic==2.10.0
  pydantic-settings==2.6.0

  # Database
  sqlalchemy==2.0.36
  alembic==1.14.0
  aiosqlite==0.20.0

  # Async HTTP
  httpx==0.28.1

  # Async Tasks
  celery==5.4.0
  redis==5.2.0

  # LLM SDKs
  openai==1.59.0
  anthropic==0.42.0

  # File Handling
  python-multipart==0.0.20
  pillow==11.1.0

  # Security
  python-jose[cryptography]==3.3.0
  passlib[bcrypt]==1.7.4
  cryptography==44.0.0

  # Logging
  structlog==24.4.0

  # Testing
  pytest==8.3.4
  pytest-asyncio==0.24.0

  # Development
  black==24.10.0
  ruff==0.8.4
  python-dotenv==1.0.1
  ```
- [ ] 创建 Python 虚拟环境
- [ ] 安装所有依赖并验证无冲突

### 2.3 环境配置

- [ ] 创建 `backend/.env.example` 环境变量模板
  ```env
  # Application
  APP_NAME=MyAI Studio
  APP_VERSION=1.0.0
  DEBUG=true
  ENVIRONMENT=development

  # Server
  HOST=0.0.0.0
  PORT=8000

  # Database
  DATABASE_URL=sqlite+aiosqlite:///./myai_studio.db

  # Celery (可选，Phase 6 启用)
  CELERY_BROKER_URL=redis://localhost:6379/0
  CELERY_RESULT_BACKEND=redis://localhost:6379/0

  # Security
  SECRET_KEY=your-secret-key-here-change-in-production
  API_KEY_ENCRYPTION_KEY=your-32-byte-encryption-key-here

  # CORS
  CORS_ORIGINS=http://localhost:3000,http://192.168.110.131:3003

  # File Storage
  UPLOAD_DIR=./storage/uploads
  MAX_UPLOAD_SIZE=524288000

  # Logging
  LOG_LEVEL=INFO
  LOG_FORMAT=json
  ```
- [ ] 创建 `backend/.env` (从 .env.example 复制并填入实际值)
- [ ] 将 `.env` 添加到 `.gitignore`

- [ ] 创建 `backend/app/config.py` 配置管理类
  - [ ] 使用 `pydantic-settings` 的 `BaseSettings`
  - [ ] 定义所有配置项的类型和默认值
  - [ ] 实现配置验证逻辑
  - [ ] 支持从 `.env` 文件和环境变量读取
  - [ ] 创建全局 `settings` 单例

### 2.4 日志配置

- [ ] 创建 `backend/app/utils/logging.py`
  - [ ] 配置 `structlog` 处理器链
  - [ ] 支持 JSON 格式输出 (生产环境)
  - [ ] 支持彩色控制台输出 (开发环境)
  - [ ] 添加请求 ID 追踪
  - [ ] 添加时间戳格式化
  - [ ] 创建 `get_logger()` 工厂函数

- [ ] 日志级别配置
  - [ ] DEBUG: 详细调试信息
  - [ ] INFO: 一般运行信息
  - [ ] WARNING: 警告信息
  - [ ] ERROR: 错误信息
  - [ ] CRITICAL: 严重错误

### 2.5 依赖注入框架

- [ ] 创建 `backend/app/dependencies.py`
  - [ ] 定义 `get_settings()` 依赖
  - [ ] 定义 `get_logger()` 依赖
  - [ ] 预留 `get_db()` 依赖占位 (Phase 2 实现)
  - [ ] 预留 `get_current_user()` 依赖占位 (可选)

### 2.6 FastAPI 应用骨架

- [ ] 创建 `backend/app/main.py`
  - [ ] 初始化 FastAPI 应用实例
  - [ ] 配置应用元数据 (title, description, version)
  - [ ] 配置 CORS 中间件
  - [ ] 添加启动事件 (lifespan)
  - [ ] 添加根路由 `/` 返回应用信息
  - [ ] 添加健康检查路由 `/health`
  - [ ] 配置 OpenAPI 文档路径

- [ ] 创建 `backend/app/api/v1/health.py`
  - [ ] 实现 `GET /api/v1/health` 端点
  - [ ] 返回应用状态、版本、环境信息

### 2.7 启动脚本

- [ ] 创建 `backend/run.py` 开发启动脚本
  ```python
  import uvicorn
  from app.config import settings

  if __name__ == "__main__":
      uvicorn.run(
          "app.main:app",
          host=settings.HOST,
          port=settings.PORT,
          reload=settings.DEBUG
      )
  ```

---

## 3. 验收标准

### 3.1 功能验收

- [ ] 执行 `python run.py` 应用成功启动
- [ ] 访问 `http://localhost:8000/` 返回应用信息 JSON
- [ ] 访问 `http://localhost:8000/health` 返回健康状态
- [ ] 访问 `http://localhost:8000/docs` 显示 Swagger UI
- [ ] 访问 `http://localhost:8000/redoc` 显示 ReDoc 文档
- [ ] 日志正确输出到控制台
- [ ] 配置从 `.env` 文件正确加载

### 3.2 代码质量

- [ ] 所有 Python 文件通过 `ruff check` 检查
- [ ] 所有 Python 文件通过 `black --check` 格式检查
- [ ] 无循环导入问题
- [ ] 类型注解完整

### 3.3 测试验收

- [ ] 创建 `backend/tests/test_health.py`
- [ ] 健康检查端点测试通过
- [ ] 配置加载测试通过

---

## 4. 目录结构预览

完成本阶段后，目录结构应如下：

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用入口
│   ├── config.py            # 配置管理
│   ├── dependencies.py      # 依赖注入
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── health.py    # 健康检查端点
│   ├── core/
│   │   └── __init__.py
│   ├── models/
│   │   └── __init__.py
│   ├── services/
│   │   └── __init__.py
│   ├── db/
│   │   └── __init__.py
│   ├── tasks/
│   │   └── __init__.py
│   └── utils/
│       ├── __init__.py
│       └── logging.py       # 日志配置
├── tests/
│   ├── __init__.py
│   └── test_health.py
├── storage/
│   ├── uploads/
│   └── cache/
├── .env.example
├── .env
├── .gitignore
├── requirements.txt
└── run.py
```

---

## 5. 注意事项

1. **不要在此阶段编写业务逻辑** - 仅搭建骨架
2. **配置必须支持环境变量覆盖** - 便于部署
3. **日志格式必须统一** - 便于后续日志分析
4. **CORS 配置必须包含前端地址** - 确保前后端联调
5. **所有敏感信息必须通过环境变量配置** - 不要硬编码

---

## 6. 下一阶段预告

完成本阶段后，进入 **Phase 2: 数据层与模型定义**，将实现：
- SQLAlchemy ORM 模型
- Pydantic 数据传输对象
- Alembic 数据库迁移
