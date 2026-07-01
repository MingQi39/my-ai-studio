"""Application configuration management.

This module provides centralized configuration management using pydantic-settings.
All configuration values can be overridden via environment variables or .env file.
"""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    All settings can be overridden via environment variables or .env file.
    Environment variables take precedence over .env file values.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Qi AI Studio"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 10011

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./myai_studio.db"

    # Celery (Phase 6)
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    API_KEY_ENCRYPTION_KEY: str = "your-32-byte-encryption-key-here"

    # CORS
    CORS_ORIGINS: str = "http://localhost:11010,http://localhost:3000,http://localhost:3001,http://localhost:5173,http://127.0.0.1:11010,http://127.0.0.1:3000,http://127.0.0.1:5173,http://192.168.110.131:11010,http://192.168.110.131:3000,http://192.168.110.131:11011"

    # File Storage
    UPLOAD_DIR: str = "./storage/uploads"
    MAX_UPLOAD_SIZE: int = 524288000  # 500MB

    # Logging
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "json"

    # Travel Agent external tools
    AMAP_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    JUHE_TRAIN_API_KEY: str = ""
    JUHE_FLIGHT_API_KEY: str = ""
    HTTP_TIMEOUT_SECONDS: int = 10
    TAVILY_MAX_RESULTS: int = 5

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def validate_cors_origins(cls, v: str | list[str]) -> str:
        """Validate and normalize CORS origins."""
        if isinstance(v, list):
            return ",".join(v)
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Settings: Application settings singleton.
    """
    return Settings()


# Global settings instance
settings = get_settings()
