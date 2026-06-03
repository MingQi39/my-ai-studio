"""
API 模块

包含所有 API 路由和中间件配置
"""
from fastapi import APIRouter

from app.api.v1 import api_router as v1_router

# 创建主路由器
api_router = APIRouter()

# 注册 v1 路由
api_router.include_router(v1_router, prefix="/v1")

__all__ = ["api_router"]
