"""
模型配置端点

提供模型配置的 CRUD 操作、验证和 Provider 信息查询
"""
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import AdapterType
from app.dependencies import get_current_user_auth, get_model_service
from app.models.schemas import (
    ModelConfigCreate,
    ModelConfigResponse,
    ModelConfigUpdate,
    ModelInfo,
)
from app.utils.logging import get_logger

if TYPE_CHECKING:
    from app.services.model_service import ModelService

router = APIRouter(prefix="/models", tags=["models"])
logger = get_logger(__name__)


@router.post("", response_model=ModelConfigResponse)
async def create_model_config(
    data: ModelConfigCreate,
    user_id: UUID = Depends(get_current_user_auth),
    model_service: "ModelService" = Depends(get_model_service),
) -> ModelConfigResponse:
    """创建模型配置"""
    config = await model_service.create_model_config(user_id, data)
    return ModelConfigResponse.from_orm(config)


@router.get("", response_model=list[ModelConfigResponse])
async def list_model_configs(
    adapter_type: AdapterType | None = Query(None, description="适配器类型筛选"),
    provider: str | None = Query(None, description="Provider 筛选（仅 OFFICIAL 类型有效）"),
    user_id: UUID = Depends(get_current_user_auth),
    model_service: "ModelService" = Depends(get_model_service),
) -> list[ModelConfigResponse]:
    """列出模型配置"""
    configs = await model_service.list_model_configs(user_id, adapter_type, provider)
    return [ModelConfigResponse.from_orm(config) for config in configs]


@router.get("/{config_id}", response_model=ModelConfigResponse)
async def get_model_config(
    config_id: UUID,
    user_id: UUID = Depends(get_current_user_auth),
    model_service: "ModelService" = Depends(get_model_service),
) -> ModelConfigResponse:
    """获取模型配置详情"""
    config = await model_service.get_model_config(config_id, user_id)
    if not config:
        raise HTTPException(status_code=404, detail="Model config not found")

    return ModelConfigResponse.from_orm(config)


@router.patch("/{config_id}", response_model=ModelConfigResponse)
async def update_model_config(
    config_id: UUID,
    data: ModelConfigUpdate,
    user_id: UUID = Depends(get_current_user_auth),
    model_service: "ModelService" = Depends(get_model_service),
) -> ModelConfigResponse:
    """更新模型配置"""
    config = await model_service.update_model_config(config_id, user_id, data)
    if not config:
        raise HTTPException(status_code=404, detail="Model config not found")

    return ModelConfigResponse.from_orm(config)


@router.delete("/{config_id}")
async def delete_model_config(
    config_id: UUID,
    user_id: UUID = Depends(get_current_user_auth),
    model_service: "ModelService" = Depends(get_model_service),
) -> dict:
    """删除模型配置"""
    success = await model_service.delete_model_config(config_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Model config not found")

    return {"success": True}


@router.post("/{config_id}/validate")
async def validate_model_config(
    config_id: UUID,
    user_id: UUID = Depends(get_current_user_auth),
    model_service: "ModelService" = Depends(get_model_service),
) -> dict:
    """验证模型配置凭证"""
    try:
        result = await model_service.validate_model_config(config_id, user_id)
        return result
    except Exception as e:
        logger.error(f"Model config validation failed: {str(e)}", exc_info=True)
        return {"valid": False, "error": str(e)}


@router.get("/{config_id}/available", response_model=list[ModelInfo])
async def list_available_models(
    config_id: UUID,
    user_id: UUID = Depends(get_current_user_auth),
    model_service: "ModelService" = Depends(get_model_service),
) -> list[ModelInfo]:
    """列出可用模型"""
    try:
        models = await model_service.list_available_models(config_id, user_id)
        return models
    except Exception as e:
        logger.error(f"Failed to list available models: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list available models")


@router.get("/adapter-types")
async def get_adapter_types() -> dict:
    """列出支持的适配器类型及 Provider 信息"""
    from app.core.config import ConfigLoader

    # 加载配置
    config_loader = ConfigLoader()

    # 构建响应
    response = {
        "official": {
            "description": "官方直连适配器（按供应商划分）",
            "providers": [],
        },
        "openrouter": {
            "description": "OpenRouter 统一网关（按模态划分）",
            "base_url": "https://openrouter.ai/api/v1",
            "requires_api_key": True,
            "text_models": [],
            "vision_models": [],
            "audio_models": [],
        },
        "ollama": {
            "description": "本地 Ollama 部署",
            "base_url": "http://localhost:11434",
            "requires_api_key": False,
            "note": "需自行安装和管理模型，通过 ollama pull 下载",
        },
        "vllm": {
            "description": "高性能本地推理引擎",
            "base_url": "http://localhost:8000/v1",
            "requires_api_key": False,
            "note": "兼容 OpenAI API，需自行部署 vLLM 服务",
        },
    }

    # 从配置文件读取官方 Provider 信息
    try:
        # 这里应该从 providers.yaml 读取，暂时返回硬编码数据
        response["official"]["providers"] = [
            {
                "id": "deepseek",
                "name": "DeepSeek",
                "base_url": "https://api.deepseek.com",
                "requires_api_key": True,
                "models": [
                    {
                        "id": "deepseek-chat",
                        "name": "DeepSeek Chat",
                        "supports_vision": False,
                        "supports_tools": True,
                        "supports_reasoning": True,
                    },
                    {
                        "id": "deepseek-reasoner",
                        "name": "DeepSeek Reasoner",
                        "supports_vision": False,
                        "supports_tools": True,
                        "supports_reasoning": True,
                    },
                ],
            },
            {
                "id": "qwen",
                "name": "Qwen (阿里云百炼)",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "requires_api_key": True,
                "models": [
                    {
                        "id": "qwen-plus",
                        "name": "Qwen Plus",
                        "supports_vision": False,
                        "supports_tools": True,
                        "supports_reasoning": False,
                    },
                    {
                        "id": "qwen3-plus",
                        "name": "Qwen3 Plus",
                        "supports_vision": False,
                        "supports_tools": True,
                        "supports_reasoning": True,
                    },
                    {
                        "id": "qwen-vl-plus",
                        "name": "Qwen VL Plus",
                        "supports_vision": True,
                        "supports_tools": True,
                        "supports_reasoning": False,
                    },
                ],
            },
        ]

        # OpenRouter 模型列表
        response["openrouter"]["text_models"] = [
            "google/gemini-3-pro-preview",
            "anthropic/claude-3.5-sonnet",
            "meta-llama/llama-3.3-70b-instruct",
        ]
        response["openrouter"]["vision_models"] = [
            "google/gemini-3-pro-image-preview",
            "google/gemini-3-pro-preview",
            "openai/gpt-4o",
        ]

    except Exception as e:
        logger.error(f"Failed to load provider config: {str(e)}", exc_info=True)

    return response
