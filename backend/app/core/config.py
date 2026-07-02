"""
配置管理

提供配置加载器和配置模型定义。
"""

import os
from enum import Enum
from pathlib import Path
from functools import lru_cache
from typing import Any

import yaml
from pydantic import BaseModel

from .exceptions import ConfigurationError


class AdapterType(str, Enum):
    """适配器类型"""
    OFFICIAL = "official"      # 官方直连
    OPENROUTER = "openrouter"  # OpenRouter 集成
    OLLAMA = "ollama"          # Ollama 本地
    VLLM = "vllm"              # vLLM 本地


class OfficialProvider(str, Enum):
    """官方直连供应商"""
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class Modality(str, Enum):
    """模态类型"""
    TEXT = "text"
    VISION = "vision"
    AUDIO = "audio"
    MULTIMODAL = "multimodal"


class ModelInfo(BaseModel):
    """模型信息"""
    id: str
    name: str
    context_length: int = 4096
    supports_vision: bool = False
    supports_tools: bool = False
    supports_reasoning: bool = False
    supports_audio: bool = False
    modality: Modality = Modality.TEXT


class ProviderConfig(BaseModel):
    """Provider 配置"""
    base_url: str
    api_key_env: str = ""
    timeout: int = 120
    max_retries: int = 3
    models: list[ModelInfo] = []


class OpenRouterConfig(BaseModel):
    """OpenRouter 配置"""
    base_url: str = "https://openrouter.ai/api/v1"
    api_key_env: str = "OPENROUTER_API_KEY"
    timeout: int = 120
    text_models: list[ModelInfo] = []
    vision_models: list[ModelInfo] = []
    audio_models: list[ModelInfo] = []


class ConfigLoader:
    """配置加载器"""

    def __init__(self, config_path: str | Path | None = None):
        if config_path is None:
            # 默认配置文件路径: backend/config/providers.yaml
            # __file__ = backend/app/core/config.py
            config_path = Path(__file__).parent.parent.parent / "config" / "providers.yaml"
        self.config_path = Path(config_path)
        self._config: dict | None = None

    def load(self) -> dict:
        """加载配置文件

        Returns:
            配置字典

        Raises:
            ConfigurationError: 配置文件不存在或格式错误
        """
        if self._config is not None:
            return self._config

        if not self.config_path.exists():
            raise ConfigurationError(
                config_key="config_path",
                reason=f"Configuration file not found: {self.config_path}"
            )

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(
                config_key="config_file",
                reason=f"Invalid YAML format: {e}"
            )

        if not isinstance(loaded, dict):
            raise ConfigurationError(
                config_key="config_file",
                reason="Configuration file must contain a YAML mapping"
            )

        self._config = loaded
        return loaded

    def reload(self) -> dict:
        """重新加载配置文件"""
        self._config = None
        return self.load()

    def get_official_provider_config(self, provider: str) -> ProviderConfig:
        """获取官方直连 Provider 配置

        Args:
            provider: 供应商名称 (deepseek, qwen, etc.)

        Returns:
            ProviderConfig 实例

        Raises:
            ConfigurationError: 供应商未配置
        """
        config = self.load()
        official = config.get("official", {})
        if provider not in official:
            raise ConfigurationError(
                config_key=f"official.{provider}",
                reason=f"Provider '{provider}' not configured"
            )

        provider_data = official[provider]
        # 转换 models 列表
        models = []
        for model_data in provider_data.get("models", []):
            # 处理 modality 字段
            if "modality" in model_data and isinstance(model_data["modality"], str):
                model_data["modality"] = Modality(model_data["modality"])
            models.append(ModelInfo(**model_data))

        return ProviderConfig(
            base_url=provider_data.get("base_url", ""),
            api_key_env=provider_data.get("api_key_env", ""),
            timeout=provider_data.get("timeout", 120),
            max_retries=provider_data.get("max_retries", 3),
            models=models,
        )

    def get_openrouter_config(self) -> OpenRouterConfig:
        """获取 OpenRouter 配置

        Returns:
            OpenRouterConfig 实例
        """
        config = self.load()
        openrouter_data = config.get("openrouter", {})

        def parse_models(models_data: list) -> list[ModelInfo]:
            models = []
            for model_data in models_data:
                if "modality" in model_data and isinstance(model_data["modality"], str):
                    model_data["modality"] = Modality(model_data["modality"])
                models.append(ModelInfo(**model_data))
            return models

        return OpenRouterConfig(
            base_url=openrouter_data.get("base_url", "https://openrouter.ai/api/v1"),
            api_key_env=openrouter_data.get("api_key_env", "OPENROUTER_API_KEY"),
            timeout=openrouter_data.get("timeout", 120),
            text_models=parse_models(openrouter_data.get("text_models", [])),
            vision_models=parse_models(openrouter_data.get("vision_models", [])),
            audio_models=parse_models(openrouter_data.get("audio_models", [])),
        )

    def get_ollama_config(self) -> ProviderConfig:
        """获取 Ollama 配置

        Returns:
            ProviderConfig 实例
        """
        config = self.load()
        ollama_data = config.get("ollama", {})

        models = []
        for model_data in ollama_data.get("models", []):
            if "modality" in model_data and isinstance(model_data["modality"], str):
                model_data["modality"] = Modality(model_data["modality"])
            models.append(ModelInfo(**model_data))

        return ProviderConfig(
            base_url=ollama_data.get("base_url", "http://localhost:11434"),
            api_key_env=ollama_data.get("api_key_env", ""),
            timeout=ollama_data.get("timeout", 300),
            max_retries=ollama_data.get("max_retries", 3),
            models=models,
        )

    def get_vllm_config(self) -> ProviderConfig:
        """获取 vLLM 配置

        Returns:
            ProviderConfig 实例
        """
        config = self.load()
        vllm_data = config.get("vllm", {})

        models = []
        for model_data in vllm_data.get("models", []):
            if "modality" in model_data and isinstance(model_data["modality"], str):
                model_data["modality"] = Modality(model_data["modality"])
            models.append(ModelInfo(**model_data))

        return ProviderConfig(
            base_url=vllm_data.get("base_url", "http://localhost:8000/v1"),
            api_key_env=vllm_data.get("api_key_env", ""),
            timeout=vllm_data.get("timeout", 300),
            max_retries=vllm_data.get("max_retries", 3),
            models=models,
        )

    @staticmethod
    def get_api_key(env_var: str) -> str:
        """从环境变量获取 API Key（必需）

        Args:
            env_var: 环境变量名称

        Returns:
            API Key

        Raises:
            ConfigurationError: 环境变量未设置
        """
        if not env_var:
            raise ConfigurationError(
                config_key="api_key_env",
                reason="API key environment variable name is empty"
            )
        key = os.getenv(env_var)
        if not key:
            raise ConfigurationError(
                config_key=env_var,
                reason=f"Environment variable '{env_var}' not set"
            )
        return key

    @staticmethod
    def get_api_key_optional(env_var: str) -> str | None:
        """从环境变量获取 API Key（可选）

        Args:
            env_var: 环境变量名称

        Returns:
            API Key 或 None
        """
        if not env_var:
            return None
        return os.getenv(env_var)


@lru_cache()
def get_config_loader() -> ConfigLoader:
    """获取配置加载器单例

    Returns:
        ConfigLoader 实例
    """
    return ConfigLoader()
