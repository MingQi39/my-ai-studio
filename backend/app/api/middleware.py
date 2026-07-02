"""
API 中间件配置

包含 CORS、请求日志、异常处理等中间件
"""
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from app.core.exceptions import LLMException
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 生成请求 ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # 记录请求开始
        start_time = time.time()
        logger.info(
            f"Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None,
            },
        )

        # 处理请求
        try:
            response = await call_next(request)
        except Exception as e:
            # 记录异常
            logger.error(
                f"Request failed: {str(e)}",
                extra={"request_id": request_id},
                exc_info=True,
            )
            raise

        # 记录请求完成
        duration = time.time() - start_time
        logger.info(
            f"Request completed",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "duration": f"{duration:.3f}s",
            },
        )

        # 添加请求 ID 到响应头
        response.headers["X-Request-ID"] = request_id

        return response


def configure_cors(app) -> None:
    """配置 CORS 中间件"""
    from app.config import settings

    # 开发环境允许所有来源，生产环境使用白名单
    if settings.is_development:
        allow_origins = ["*"]
    else:
        allow_origins = settings.cors_origins_list

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True if not settings.is_development else False,  # 允许所有来源时不能使用 credentials
        allow_methods=["*"],
        allow_headers=["*"],
    )


def configure_logging_middleware(app) -> None:
    """配置请求日志中间件"""
    app.add_middleware(RequestLoggingMiddleware)


async def llm_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """LLM 异常处理器"""
    if not isinstance(exc, LLMException):
        raise exc

    logger.error(
        f"LLM Exception: {exc.error_code}",
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details,
            "timestamp": exc.timestamp.isoformat(),
        },
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """请求验证异常处理器"""
    from fastapi.exceptions import RequestValidationError

    if not isinstance(exc, RequestValidationError):
        raise exc

    logger.warning(
        f"Validation error",
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "errors": exc.errors(),
        },
    )

    return JSONResponse(
        status_code=400,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": exc.errors(),
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """通用异常处理器"""
    logger.error(
        f"Unhandled exception: {str(exc)}",
        extra={"request_id": getattr(request.state, "request_id", None)},
        exc_info=True,
    )

    # 获取CORS配置
    from app.config import settings

    # 创建响应并添加CORS头
    response = JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred",
            "details": str(exc) if settings.DEBUG else None,  # 开发环境显示详细错误
        },
    )

    # 添加CORS头
    origin = request.headers.get("origin")
    if origin and origin in settings.cors_origins_list:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"

    return response
