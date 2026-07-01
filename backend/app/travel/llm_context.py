"""Resolve OpenAI-compatible credentials from a user's model config."""

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status

from app.core.config import ConfigLoader, AdapterType
from app.core.exceptions import ConfigurationError
from app.services.model_service import ModelService, decrypt_api_key


@dataclass
class TravelLLMContext:
    api_key: str
    base_url: str
    model_id: str


def _default_base_url(adapter_type: str, provider: str | None) -> str:
    if adapter_type == AdapterType.OPENROUTER.value:
        return "https://openrouter.ai/api/v1"
    if adapter_type == AdapterType.OLLAMA.value:
        return "http://localhost:11434/v1"
    if adapter_type == AdapterType.VLLM.value:
        return "http://localhost:8000/v1"

    if provider:
        loader = ConfigLoader()
        try:
            provider_cfg = loader.get_official_provider_config(provider)
            if provider_cfg.base_url:
                base = provider_cfg.base_url
                return base if base.endswith("/v1") else f"{base.rstrip('/')}/v1"
        except ConfigurationError:
            pass

    return "https://api.openai.com/v1"


async def resolve_travel_llm(
    model_service: ModelService,
    user_id: UUID,
    model_config_id: UUID,
) -> TravelLLMContext:
    config = await model_service.get_model_config(model_config_id, user_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型配置不存在，请先在设置中配置模型连接",
        )

    try:
        api_key = decrypt_api_key(config.encrypted_api_key)
    except ConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    base_url = config.base_url or _default_base_url(config.adapter_type, config.provider)
    if not base_url.endswith("/v1"):
        base_url = f"{base_url.rstrip('/')}/v1"

    return TravelLLMContext(
        api_key=api_key,
        base_url=base_url,
        model_id=config.model_id,
    )
