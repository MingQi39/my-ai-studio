"""
简化的 main.py 用于测试 API 路由

暂时移除服务层依赖，只测试路由注册
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.api.middleware import (
    configure_cors,
    configure_logging_middleware,
    general_exception_handler,
    llm_exception_handler,
    validation_exception_handler,
)
from app.config import settings
from app.core.exceptions import LLMException
from app.utils.logging import get_logger, setup_logging

# 初始化日志
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理器"""
    logger.info(
        "Starting application",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )
    # 暂时不初始化数据库
    # await init_db()
    logger.info("Application started (database initialization skipped for testing)")
    yield
    # await close_db()
    logger.info("Shutting down application")


# 配置 OpenAPI 标签元数据
tags_metadata = [
    {"name": "health", "description": "健康检查"},
    {"name": "sessions", "description": "会话管理"},
    {"name": "chat", "description": "聊天接口"},
    {"name": "models", "description": "模型配置"},
    {"name": "files", "description": "文件管理"},
    {"name": "batch", "description": "批处理任务"},
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

# 只注册健康检查和模型配置端点（不依赖服务层）
from fastapi import APIRouter
from app.api.v1 import health, models

api_router = APIRouter()
v1_router = APIRouter()
v1_router.include_router(health.router, tags=["health"])
v1_router.include_router(models.router, tags=["models"])
api_router.include_router(v1_router, prefix="/v1")

app.include_router(api_router, prefix="/api")


@app.get("/")
async def root() -> dict:
    """根端点"""
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
    """快速健康检查端点（根级别）"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
