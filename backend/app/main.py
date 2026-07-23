"""
FastAPI 应用入口

初始化 FastAPI 应用，配置中间件、路由和异常处理器
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.api import api_router
from app.api.middleware import (
    configure_cors,
    configure_logging_middleware,
    general_exception_handler,
    llm_exception_handler,
    validation_exception_handler,
)
from app.config import settings
from app.core.exceptions import LLMException
from app.db.database import close_db, init_db
from app.utils.logging import get_logger, setup_logging

# 初始化日志
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理器

    处理启动和关闭事件

    Args:
        app: FastAPI 应用实例

    Yields:
        None
    """
    # 启动时执行
    logger.info(
        "Starting application",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )
    # 注意：数据库初始化由 Alembic 迁移管理，不需要自动建表
    # await init_db()
    from app.interview.push_scheduler import start_interview_push_scheduler

    start_interview_push_scheduler()
    logger.info("Application started (database managed by Alembic)")
    yield
    # 关闭时执行
    from app.interview.push_scheduler import stop_interview_push_scheduler

    await stop_interview_push_scheduler()
    await close_db()
    logger.info("Database connection closed")
    logger.info("Shutting down application")


# 配置 OpenAPI 标签元数据
tags_metadata = [
    {"name": "health", "description": "健康检查"},
    {"name": "sessions", "description": "会话管理"},
    {"name": "chat", "description": "聊天接口"},
    {"name": "models", "description": "模型配置"},
    {"name": "files", "description": "文件管理"},
    {"name": "batch", "description": "批处理任务"},
    {"name": "travel", "description": "旅行规划 Agent（ReAct / 工具 / 对比）"},
]

# 创建 FastAPI 应用
app = FastAPI(
    title="Qi AI Studio API",
    description="通用大模型接入平台后端服务 - 支持多模型适配、流式响应、批处理任务等功能",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

# 配置中间件
configure_cors(app)
configure_logging_middleware(app)

# 配置异常处理器
app.add_exception_handler(LLMException, llm_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# 注册 API 路由
app.include_router(api_router, prefix="/api")


@app.get("/")
async def root() -> dict:
    """根端点

    返回应用信息

    Returns:
        dict: 应用信息
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "health_url": "/api/v1/health",
    }


@app.get("/health")
async def health() -> dict:
    """快速健康检查端点（根级别）

    Returns:
        dict: 健康状态
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
