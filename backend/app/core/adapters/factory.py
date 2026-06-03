"""
适配器工厂

提供统一的适配器创建接口。
"""

from __future__ import annotations

import os
import pathlib
from typing import Any

import yaml

from .base import BaseLLMAdapter
from .official import DeepSeekAdapter, QwenAdapter, OpenAICompatibleAdapter
from .openrouter import OpenRouterAdapter
from .ollama import OllamaAdapter
from .vllm import VLLMAdapter
from .omp import OmpAdapter
from ..config import (
    AdapterType,
    OfficialProvider,
    ConfigLoader,
    get_config_loader,
)
from ..exceptions import ConfigurationError


_OMP_MODELS_FILE = pathlib.Path.home() / ".omp" / "agent" / "models.yml"


def _resolve_omp_api_key(base_url: str) -> str | None:
    """从本机 ~/.omp/agent/models.yml 解析与 base_url 匹配的 apiKey。

    omp 的 apiKey 字段约定写环境变量名，本函数：
    1) 读取 yml；
    2) 找 baseUrl == base_url 的 provider；
    3) 用其 apiKey 作为环境变量名读取实际 key；
    若文件不存在 / 不匹配 / 环境变量未设置，返回 None。
    """
    if not _OMP_MODELS_FILE.exists():
        return None
    try:
        with _OMP_MODELS_FILE.open("r", encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
    except yaml.YAMLError:
        return None
    providers = doc.get("providers") or {}
    if not isinstance(providers, dict):
        return None
    target = base_url.rstrip("/")
    for spec in providers.values():
        if not isinstance(spec, dict):
            continue
        if str(spec.get("baseUrl", "")).rstrip("/") != target:
            continue
        api_spec = spec.get("apiKey")
        if not api_spec or not isinstance(api_spec, str):
            return None
        # 环境变量名约定：纯大写下划线
        if api_spec.replace("_", "").isalnum() and api_spec.isupper():
            return os.getenv(api_spec)
        # 也兼容直接写 key 的场景
        return api_spec
    return None


class LLMAdapterFactory:
    """LLM 适配器工厂

    提供统一的适配器创建接口。
    """

    # 官方直连适配器映射
    _official_adapters: dict[str, type[BaseLLMAdapter]] = {
        OfficialProvider.DEEPSEEK.value: DeepSeekAdapter,
        OfficialProvider.QWEN.value: QwenAdapter,
        OfficialProvider.OPENAI.value: OpenAICompatibleAdapter,
        OfficialProvider.ANTHROPIC.value: OpenAICompatibleAdapter,
        OfficialProvider.GEMINI.value: OpenAICompatibleAdapter,
    }

    # 适配器类型映射
    _adapter_types: dict[str, type[BaseLLMAdapter]] = {
        AdapterType.OPENROUTER.value: OpenRouterAdapter,
        AdapterType.OLLAMA.value: OllamaAdapter,
        AdapterType.VLLM.value: VLLMAdapter,
        AdapterType.OMP.value: OmpAdapter,
    }

    def __init__(self, config_loader: ConfigLoader | None = None):
        """初始化工厂

        Args:
            config_loader: 配置加载器，默认使用全局单例
        """
        self.config_loader = config_loader or get_config_loader()

    def create_official(
        self,
        provider: str | OfficialProvider,
        model_id: str,
        **kwargs: Any,
    ) -> BaseLLMAdapter:
        """创建官方直连适配器

        Args:
            provider: 供应商名称 (deepseek, qwen, etc.)
            model_id: 模型 ID
            **kwargs: 其他参数

        Returns:
            适配器实例

        Raises:
            ConfigurationError: 供应商未配置或不支持
        """
        provider_name = provider.value if isinstance(provider, OfficialProvider) else provider

        # 获取适配器类
        adapter_class = self._official_adapters.get(provider_name)
        if not adapter_class:
            raise ConfigurationError(
                config_key=f"official.{provider_name}",
                reason=f"Provider '{provider_name}' not supported"
            )

        # 获取配置
        provider_config = self.config_loader.get_official_provider_config(provider_name)

        # 获取 API Key
        api_key = kwargs.pop("api_key", None)
        if not api_key:
            api_key = self.config_loader.get_api_key(provider_config.api_key_env)

        # 创建适配器
        return adapter_class(
            api_key=api_key,
            base_url=kwargs.pop("base_url", provider_config.base_url),
            model_id=model_id,
            timeout=kwargs.pop("timeout", provider_config.timeout),
            **kwargs,
        )

    def create_openrouter(
        self,
        model_id: str,
        **kwargs: Any,
    ) -> OpenRouterAdapter:
        """创建 OpenRouter 适配器

        Args:
            model_id: 模型 ID (格式: provider/model-name)
            **kwargs: 其他参数

        Returns:
            OpenRouterAdapter 实例
        """
        # 获取配置
        openrouter_config = self.config_loader.get_openrouter_config()

        # 获取 API Key
        api_key = kwargs.pop("api_key", None)
        if not api_key:
            api_key = self.config_loader.get_api_key(openrouter_config.api_key_env)

        return OpenRouterAdapter(
            api_key=api_key,
            base_url=kwargs.pop("base_url", openrouter_config.base_url),
            model_id=model_id,
            timeout=kwargs.pop("timeout", openrouter_config.timeout),
            **kwargs,
        )

    def create_ollama(
        self,
        model_id: str,
        **kwargs: Any,
    ) -> OllamaAdapter:
        """创建 Ollama 适配器

        Args:
            model_id: 模型 ID
            **kwargs: 其他参数

        Returns:
            OllamaAdapter 实例
        """
        # 获取配置
        ollama_config = self.config_loader.get_ollama_config()

        # Ollama 通常不需要 API Key
        api_key = kwargs.pop("api_key", "")
        if not api_key and ollama_config.api_key_env:
            api_key = self.config_loader.get_api_key_optional(ollama_config.api_key_env) or ""

        return OllamaAdapter(
            api_key=api_key,
            base_url=kwargs.pop("base_url", ollama_config.base_url),
            model_id=model_id,
            timeout=kwargs.pop("timeout", ollama_config.timeout),
            **kwargs,
        )

    def create_vllm(
        self,
        model_id: str,
        **kwargs: Any,
    ) -> VLLMAdapter:
        """创建 vLLM 适配器

        Args:
            model_id: 模型 ID
            **kwargs: 其他参数

        Returns:
            VLLMAdapter 实例
        """
        # 获取配置
        vllm_config = self.config_loader.get_vllm_config()

        # vLLM 通常不需要 API Key
        api_key = kwargs.pop("api_key", "")
        if not api_key and vllm_config.api_key_env:
            api_key = self.config_loader.get_api_key_optional(vllm_config.api_key_env) or ""

        return VLLMAdapter(
            api_key=api_key,
            base_url=kwargs.pop("base_url", vllm_config.base_url),
            model_id=model_id,
            timeout=kwargs.pop("timeout", vllm_config.timeout),
            **kwargs,
        )

    def create_omp(
        self,
        model_id: str,
        **kwargs: Any,
    ) -> OmpAdapter:
        """创建 OMP / One Hub OpenAI-兼容适配器

        Args:
            model_id: 模型 ID（应当存在于 ~/.omp/agent/models.yml）
            **kwargs: 必须传入 base_url；api_key 可省略，缺失时从本机
                      ~/.omp/agent/models.yml 中匹配 base_url 的 provider
                      解析其 apiKey 字段（环境变量名）后从环境变量读取。
        """
        api_key = kwargs.pop("api_key", "") or ""
        base_url = kwargs.pop("base_url", None)
        if not base_url:
            raise ConfigurationError(
                config_key="base_url",
                reason="OMP adapter requires base_url from ModelConfig",
            )

        if not api_key:
            api_key = _resolve_omp_api_key(base_url) or ""

        return OmpAdapter(
            api_key=api_key,
            base_url=base_url,
            model_id=model_id,
            timeout=kwargs.pop("timeout", 120),
        )

    def create(
        self,
        adapter_type: str | AdapterType,
        model_id: str,
        provider: str | OfficialProvider | None = None,
        **kwargs: Any,
    ) -> BaseLLMAdapter:
        """通用创建方法

        Args:
            adapter_type: 适配器类型 (official, openrouter, ollama, vllm)
            model_id: 模型 ID
            provider: 供应商名称（仅 official 类型需要）
            **kwargs: 其他参数

        Returns:
            适配器实例

        Raises:
            ConfigurationError: 适配器类型不支持
        """
        type_name = adapter_type.value if isinstance(adapter_type, AdapterType) else adapter_type

        if type_name == AdapterType.OFFICIAL.value:
            if not provider:
                raise ConfigurationError(
                    config_key="provider",
                    reason="Provider is required for official adapter"
                )
            return self.create_official(provider, model_id, **kwargs)
        elif type_name == AdapterType.OPENROUTER.value:
            return self.create_openrouter(model_id, **kwargs)
        elif type_name == AdapterType.OLLAMA.value:
            return self.create_ollama(model_id, **kwargs)
        elif type_name == AdapterType.VLLM.value:
            return self.create_vllm(model_id, **kwargs)
        elif type_name == AdapterType.OMP.value:
            return self.create_omp(model_id, **kwargs)
        else:
            raise ConfigurationError(
                config_key="adapter_type",
                reason=f"Adapter type '{type_name}' not supported"
            )


# 全局工厂实例
adapter_factory = LLMAdapterFactory()
