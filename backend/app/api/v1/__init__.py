"""
API v1 模块

聚合所有 v1 版本的 API 端点
"""
from fastapi import APIRouter

# 导入所有端点
from app.api.v1 import auth, batch, chat, files, fitness, health, models, models_info, sessions, spider, system_instructions, travel

# 创建 v1 路由器（不带前缀，前缀在主路由中添加）
api_router = APIRouter()

# 注册所有子路由
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(sessions.router, tags=["sessions"])
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(models.router, tags=["models"])
api_router.include_router(models_info.router, tags=["models-info"])
api_router.include_router(files.router, tags=["files"])
api_router.include_router(batch.router, tags=["batch"])
api_router.include_router(system_instructions.router, tags=["system-instructions"])
api_router.include_router(travel.router, tags=["travel"])
api_router.include_router(fitness.router, tags=["fitness"])
api_router.include_router(spider.router, tags=["spider"])

__all__ = ["api_router"]
