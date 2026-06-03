"""Health check endpoints.

This module provides health check endpoints for monitoring application status.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.config import Settings
from app.dependencies import get_settings_dependency

router = APIRouter()


@router.get("/health")
async def health_check(
    settings: Settings = Depends(get_settings_dependency),
) -> dict:
    """Health check endpoint.

    Returns application status, version, and environment information.

    Returns:
        dict: Health status information.
    """
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ready")
async def readiness_check(
    settings: Settings = Depends(get_settings_dependency),
) -> dict:
    """Readiness check endpoint.

    Checks if the application is ready to serve requests.
    This endpoint can be extended to check database connectivity, etc.

    Returns:
        dict: Readiness status information.
    """
    # TODO: Add database connectivity check in Phase 2
    # TODO: Add Redis connectivity check in Phase 6
    checks = {
        "database": "not_configured",  # Will be updated in Phase 2
        "redis": "not_configured",  # Will be updated in Phase 6
    }

    return {
        "status": "ready",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
