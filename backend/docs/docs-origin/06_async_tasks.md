# Phase 6: 异步任务与部署

> **目标**: 启用后台处理能力并完成系统组装，实现生产就绪的部署配置。
> **预计工时**: 2-3 天
> **前置依赖**: Phase 5 完成

---

## 1. 阶段概述

本阶段聚焦于 Celery 异步任务配置、Redis 连接、批处理任务执行逻辑，以及 Docker 部署配置。完成后，系统应具备完整的后台处理能力和生产部署能力。

---

## 2. 任务清单

### 2.1 Redis 连接配置

- [ ] 更新 `backend/app/config.py`
  - [ ] 添加 Redis 配置项
  ```python
  REDIS_URL: str = "redis://localhost:6379/0"
  CELERY_BROKER_URL: str = "redis://localhost:6379/0"
  CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
  ```

- [ ] 创建 `backend/app/utils/redis.py`
  - [ ] 实现 Redis 连接池
  - [ ] 实现 `get_redis()` 依赖
  - [ ] 实现连接健康检查

### 2.2 Celery 配置

- [ ] 创建 `backend/app/tasks/celery_app.py`

#### 2.2.1 Celery 应用初始化

- [ ] 配置 Celery 应用
  ```python
  from celery import Celery
  from app.config import settings

  celery_app = Celery(
      "myai_studio",
      broker=settings.CELERY_BROKER_URL,
      backend=settings.CELERY_RESULT_BACKEND,
      include=["app.tasks.celery_tasks"]
  )
  ```

- [ ] 配置 Celery 选项
  ```python
  celery_app.conf.update(
      task_serializer="json",
      accept_content=["json"],
      result_serializer="json",
      timezone="UTC",
      enable_utc=True,
      task_track_started=True,
      task_time_limit=3600,  # 1 小时超时
      task_soft_time_limit=3300,  # 55 分钟软超时
      worker_prefetch_multiplier=1,  # 公平调度
      task_acks_late=True,  # 任务完成后确认
      task_reject_on_worker_lost=True,
  )
  ```

#### 2.2.2 任务路由配置

- [ ] 配置任务队列
  ```python
  celery_app.conf.task_routes = {
      "app.tasks.celery_tasks.process_batch_item": {"queue": "batch"},
      "app.tasks.celery_tasks.cleanup_old_sessions": {"queue": "maintenance"},
      "app.tasks.celery_tasks.generate_summary": {"queue": "default"},
  }
  ```

- [ ] 配置队列优先级
  ```python
  celery_app.conf.task_queues = (
      Queue("default", routing_key="default"),
      Queue("batch", routing_key="batch"),
      Queue("maintenance", routing_key="maintenance"),
  )
  ```

### 2.3 Celery 任务定义

- [ ] 创建 `backend/app/tasks/celery_tasks.py`

#### 2.3.1 批处理任务

- [ ] 实现 `process_batch_item` 任务
  ```python
  @celery_app.task(
      bind=True,
      max_retries=3,
      default_retry_delay=60,
      autoretry_for=(ProviderConnectionError, ProviderTimeoutError),
      retry_backoff=True
  )
  def process_batch_item(
      self,
      item_id: str,
      model_config_id: str,
      prompt: str,
      system_prompt: str | None = None,
      temperature: float = 0.7,
      max_tokens: int | None = None
  ) -> dict:
      """处理单个批处理项"""
      ...
  ```

- [ ] 实现任务内部逻辑
  - [ ] 获取数据库会话 (同步)
  - [ ] 获取模型配置
  - [ ] 创建适配器
  - [ ] 调用 LLM API (同步包装)
  - [ ] 更新批处理项状态
  - [ ] 更新批处理任务计数
  - [ ] 返回结果

- [ ] 实现 `start_batch_job` 任务
  ```python
  @celery_app.task(bind=True)
  def start_batch_job(self, batch_id: str) -> dict:
      """启动批处理任务，分发所有项"""
      # 获取批处理任务
      # 更新状态为 running
      # 为每个项创建子任务
      # 使用 group 或 chord 并行执行
      ...
  ```

- [ ] 实现 `finalize_batch_job` 任务
  ```python
  @celery_app.task(bind=True)
  def finalize_batch_job(self, batch_id: str) -> dict:
      """完成批处理任务，更新最终状态"""
      ...
  ```

#### 2.3.2 维护任务

- [ ] 实现 `cleanup_old_sessions` 任务
  ```python
  @celery_app.task
  def cleanup_old_sessions(days: int = 30) -> dict:
      """清理超过指定天数的已归档会话"""
      ...
  ```

- [ ] 实现 `cleanup_orphan_files` 任务
  ```python
  @celery_app.task
  def cleanup_orphan_files() -> dict:
      """清理无引用的孤立文件"""
      ...
  ```

- [ ] 实现 `generate_session_summary` 任务
  ```python
  @celery_app.task
  def generate_session_summary(session_id: str) -> dict:
      """为会话生成摘要标题"""
      ...
  ```

#### 2.3.3 健康检查任务

- [ ] 实现 `health_check` 任务
  ```python
  @celery_app.task
  def health_check() -> dict:
      """Celery 健康检查"""
      return {
          "status": "healthy",
          "timestamp": datetime.utcnow().isoformat()
      }
  ```

### 2.4 Celery Beat 定时任务

- [ ] 配置定时任务调度
  ```python
  celery_app.conf.beat_schedule = {
      "cleanup-old-sessions": {
          "task": "app.tasks.celery_tasks.cleanup_old_sessions",
          "schedule": crontab(hour=2, minute=0),  # 每天凌晨 2 点
          "args": (30,)  # 30 天
      },
      "cleanup-orphan-files": {
          "task": "app.tasks.celery_tasks.cleanup_orphan_files",
          "schedule": crontab(hour=3, minute=0),  # 每天凌晨 3 点
      },
      "health-check": {
          "task": "app.tasks.celery_tasks.health_check",
          "schedule": 300.0,  # 每 5 分钟
      },
  }
  ```

### 2.5 批处理服务集成

- [ ] 更新 `backend/app/services/batch_service.py`

- [ ] 实现 `start_batch_processing(batch_id: UUID, user_id: UUID) -> BatchJob`
  - [ ] 验证任务归属
  - [ ] 调用 Celery 任务
  - [ ] 返回更新后的任务

- [ ] 实现任务状态回调
  - [ ] 监听任务完成事件
  - [ ] 更新数据库状态

### 2.6 API 集成

- [ ] 更新 `backend/app/api/v1/batch.py`

- [ ] 实现 `POST /api/v1/batch/{batch_id}/start`
  - [ ] 启动批处理任务
  - [ ] 返回任务状态

- [ ] 更新健康检查端点
  - [ ] 添加 Celery 状态检查
  - [ ] 添加 Redis 状态检查

### 2.7 Dockerfile

- [ ] 创建 `backend/Dockerfile`
  ```dockerfile
  FROM python:3.11-slim

  WORKDIR /app

  # 安装系统依赖
  RUN apt-get update && apt-get install -y \
      gcc \
      libpq-dev \
      && rm -rf /var/lib/apt/lists/*

  # 复制依赖文件
  COPY requirements.txt .

  # 安装 Python 依赖
  RUN pip install --no-cache-dir -r requirements.txt

  # 复制应用代码
  COPY . .

  # 创建存储目录
  RUN mkdir -p /app/storage/uploads /app/storage/cache

  # 暴露端口
  EXPOSE 8000

  # 启动命令
  CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
  ```

- [ ] 创建 `backend/.dockerignore`
  ```
  __pycache__
  *.pyc
  *.pyo
  .env
  .git
  .gitignore
  *.md
  tests/
  .pytest_cache/
  .coverage
  htmlcov/
  venv/
  .venv/
  ```

### 2.8 Docker Compose

- [ ] 创建 `docker-compose.yml` (项目根目录)
  ```yaml
  version: "3.8"

  services:
    # 后端 API 服务
    backend:
      build:
        context: ./backend
        dockerfile: Dockerfile
      ports:
        - "8000:8000"
      volumes:
        - ./backend/storage:/app/storage
        - backend_db:/app/data
      environment:
        - DATABASE_URL=sqlite+aiosqlite:///./data/myai_studio.db
        - CELERY_BROKER_URL=redis://redis:6379/0
        - CELERY_RESULT_BACKEND=redis://redis:6379/1
        - REDIS_URL=redis://redis:6379/0
        - CORS_ORIGINS=http://localhost:3000,http://192.168.110.131:3003
      depends_on:
        - redis
      restart: unless-stopped

    # Celery Worker
    celery-worker:
      build:
        context: ./backend
        dockerfile: Dockerfile
      command: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4
      volumes:
        - ./backend/storage:/app/storage
        - backend_db:/app/data
      environment:
        - DATABASE_URL=sqlite+aiosqlite:///./data/myai_studio.db
        - CELERY_BROKER_URL=redis://redis:6379/0
        - CELERY_RESULT_BACKEND=redis://redis:6379/1
      depends_on:
        - redis
      restart: unless-stopped

    # Celery Beat (定时任务)
    celery-beat:
      build:
        context: ./backend
        dockerfile: Dockerfile
      command: celery -A app.tasks.celery_app beat --loglevel=info
      volumes:
        - backend_db:/app/data
      environment:
        - DATABASE_URL=sqlite+aiosqlite:///./data/myai_studio.db
        - CELERY_BROKER_URL=redis://redis:6379/0
        - CELERY_RESULT_BACKEND=redis://redis:6379/1
      depends_on:
        - redis
      restart: unless-stopped

    # Redis
    redis:
      image: redis:7-alpine
      ports:
        - "6379:6379"
      volumes:
        - redis_data:/data
      restart: unless-stopped

    # 前端 (可选，开发时可单独运行)
    frontend:
      build:
        context: ./frontend
        dockerfile: Dockerfile
      ports:
        - "3000:3000"
      depends_on:
        - backend
      restart: unless-stopped

  volumes:
    backend_db:
    redis_data:
  ```

### 2.9 前端 Dockerfile (可选)

- [ ] 创建 `frontend/Dockerfile`
  ```dockerfile
  FROM node:20-alpine AS builder

  WORKDIR /app

  COPY package*.json ./
  RUN npm ci

  COPY . .
  RUN npm run build

  FROM nginx:alpine

  COPY --from=builder /app/build /usr/share/nginx/html
  COPY nginx.conf /etc/nginx/conf.d/default.conf

  EXPOSE 3000

  CMD ["nginx", "-g", "daemon off;"]
  ```

- [ ] 创建 `frontend/nginx.conf`
  ```nginx
  server {
      listen 3000;
      server_name localhost;

      root /usr/share/nginx/html;
      index index.html;

      location / {
          try_files $uri $uri/ /index.html;
      }

      location /api {
          proxy_pass http://backend:8000;
          proxy_http_version 1.1;
          proxy_set_header Upgrade $http_upgrade;
          proxy_set_header Connection 'upgrade';
          proxy_set_header Host $host;
          proxy_cache_bypass $http_upgrade;
          proxy_buffering off;  # SSE 需要
      }
  }
  ```

### 2.10 部署脚本

- [ ] 创建 `scripts/start-dev.sh`
  ```bash
  #!/bin/bash
  # 开发环境启动脚本

  # 启动 Redis
  redis-server --daemonize yes

  # 启动 Celery Worker
  cd backend
  celery -A app.tasks.celery_app worker --loglevel=info &

  # 启动 Celery Beat
  celery -A app.tasks.celery_app beat --loglevel=info &

  # 启动后端
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &

  # 启动前端
  cd ../frontend
  npm run dev
  ```

- [ ] 创建 `scripts/start-prod.sh`
  ```bash
  #!/bin/bash
  # 生产环境启动脚本

  docker-compose up -d
  ```

- [ ] 创建 `scripts/stop.sh`
  ```bash
  #!/bin/bash
  # 停止所有服务

  docker-compose down
  ```

### 2.11 环境配置文件

- [ ] 创建 `backend/.env.production`
  ```env
  APP_NAME=MyAI Studio
  APP_VERSION=1.0.0
  DEBUG=false
  ENVIRONMENT=production

  HOST=0.0.0.0
  PORT=8000

  DATABASE_URL=sqlite+aiosqlite:///./data/myai_studio.db

  CELERY_BROKER_URL=redis://redis:6379/0
  CELERY_RESULT_BACKEND=redis://redis:6379/1
  REDIS_URL=redis://redis:6379/0

  SECRET_KEY=your-production-secret-key
  API_KEY_ENCRYPTION_KEY=your-production-encryption-key

  CORS_ORIGINS=https://your-domain.com

  UPLOAD_DIR=/app/storage/uploads
  MAX_UPLOAD_SIZE=524288000

  LOG_LEVEL=INFO
  LOG_FORMAT=json
  ```

### 2.12 README 更新

- [ ] 创建 `backend/README.md`
  ```markdown
  # MyAI Studio Backend

  ## 快速开始

  ### 开发环境

  1. 创建虚拟环境
  ```bash
  python -m venv venv
  source venv/bin/activate
  ```

  2. 安装依赖
  ```bash
  pip install -r requirements.txt
  ```

  3. 配置环境变量
  ```bash
  cp .env.example .env
  # 编辑 .env 文件
  ```

  4. 初始化数据库
  ```bash
  alembic upgrade head
  ```

  5. 启动服务
  ```bash
  # 启动 Redis
  redis-server

  # 启动 Celery Worker
  celery -A app.tasks.celery_app worker --loglevel=info

  # 启动后端
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  ```

  ### Docker 部署

  ```bash
  docker-compose up -d
  ```

  ## API 文档

  - Swagger UI: http://localhost:8000/docs
  - ReDoc: http://localhost:8000/redoc
  ```

### 2.13 任务导出

- [ ] 更新 `backend/app/tasks/__init__.py`
  - [ ] 导出 celery_app
  - [ ] 导出所有任务

---

## 3. 验收标准

### 3.1 功能验收

- [ ] Redis 连接正常
- [ ] Celery Worker 启动正常
- [ ] Celery Beat 启动正常
- [ ] 批处理任务可创建并执行
- [ ] 定时任务按计划执行
- [ ] Docker 容器构建成功
- [ ] Docker Compose 启动所有服务

### 3.2 集成验收

- [ ] 前端可通过 API 创建批处理任务
- [ ] 批处理任务状态实时更新
- [ ] 健康检查包含所有组件状态
- [ ] 日志正确输出

### 3.3 部署验收

- [ ] `docker-compose up` 一键启动
- [ ] 服务重启后数据持久化
- [ ] 环境变量正确加载
- [ ] 端口映射正确

### 3.4 测试验收

- [ ] 创建 `backend/tests/test_celery_tasks.py`
- [ ] 批处理任务测试通过
- [ ] 定时任务测试通过

---

## 4. 目录结构预览

完成本阶段后，完整项目结构应如下：

```
my-ai-studio/
├── frontend/                    # 前端项目
│   ├── src/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── ...
├── backend/                     # 后端项目
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── dependencies.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── middleware.py
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── health.py
│   │   │       ├── sessions.py
│   │   │       ├── chat.py
│   │   │       ├── models.py
│   │   │       ├── files.py
│   │   │       └── batch.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── exceptions.py
│   │   │   ├── retry.py
│   │   │   ├── security.py
│   │   │   ├── streaming.py
│   │   │   └── adapters/
│   │   │       ├── __init__.py
│   │   │       ├── base.py
│   │   │       ├── openai_adapter.py
│   │   │       ├── anthropic_adapter.py
│   │   │       └── ollama_adapter.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── database.py
│   │   │   └── schemas.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── session_service.py
│   │   │   ├── model_service.py
│   │   │   ├── chat_service.py
│   │   │   ├── file_service.py
│   │   │   └── batch_service.py
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── database.py
│   │   │   └── migrations/
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py
│   │   │   └── celery_tasks.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── logging.py
│   │       ├── redis.py
│   │       └── metrics.py
│   ├── tests/
│   ├── storage/
│   │   ├── uploads/
│   │   └── cache/
│   ├── .env.example
│   ├── .env.production
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── alembic.ini
│   └── README.md
├── scripts/
│   ├── start-dev.sh
│   ├── start-prod.sh
│   └── stop.sh
├── docker-compose.yml
├── CLAUDE.md
└── README.md
```

---

## 5. 注意事项

1. **Celery 任务要幂等** - 支持重试
2. **数据库连接要同步** - Celery 任务中使用同步 SQLAlchemy
3. **任务超时要合理** - LLM 调用可能较慢
4. **Redis 要持久化** - 防止任务丢失
5. **Docker 卷要正确映射** - 数据持久化
6. **环境变量要分离** - 开发/生产配置分开
7. **日志要集中** - 便于问题排查

---

## 6. 后续扩展

完成所有 6 个阶段后，系统已具备完整功能。后续可扩展：

1. **EvalScope 集成** - 模型评测插件
2. **Canvas 功能** - 工作流编排
3. **RAG 支持** - 向量数据库集成
4. **用户认证** - JWT Token 认证
5. **API 限流** - 防止滥用
6. **监控告警** - Prometheus + Grafana
7. **日志聚合** - ELK Stack
