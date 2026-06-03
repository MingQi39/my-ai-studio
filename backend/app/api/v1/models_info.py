"""
模型信息端点（不依赖服务层）

提供适配器类型和 Provider 信息查询
"""
from fastapi import APIRouter

from app.utils.logging import get_logger

router = APIRouter(prefix="/models", tags=["models"])
logger = get_logger(__name__)


@router.get("/adapter-types")
async def get_adapter_types() -> dict:
    """列出支持的适配器类型及 Provider 信息"""
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
