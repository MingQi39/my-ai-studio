"""Tests for health check endpoints."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app


@pytest_asyncio.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test root endpoint returns application info."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == settings.APP_NAME
    assert data["version"] == settings.APP_VERSION
    assert "docs_url" in data
    assert "health_url" in data


@pytest.mark.asyncio
async def test_root_health_endpoint(client: AsyncClient):
    """Test root level health endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_api_health_endpoint(client: AsyncClient):
    """Test API v1 health endpoint."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == settings.APP_VERSION
    assert data["environment"] == settings.ENVIRONMENT
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_api_health_ready_endpoint(client: AsyncClient):
    """Test API v1 readiness endpoint."""
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "checks" in data
    assert "timestamp" in data


def test_settings_loaded():
    """Test that settings are loaded correctly."""
    assert settings.APP_NAME == "MyAI Studio"
    assert settings.HOST == "0.0.0.0"
    assert settings.PORT == 10011
    assert len(settings.cors_origins_list) > 0
