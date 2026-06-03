"""
OMP / One Hub 本地配置探查端点

读取本机 `~/.omp/agent/models.yml`，把用户在 omp 中已经配置好的
provider / models / api_key 环境变量等信息直接暴露给前端，让用户
不必重复填写，可以直接选模型并保存配置。

设计要点：
- 不返回真实 API Key 内容；仅返回环境变量名以及该变量是否在
  服务进程内可解析（avoid 泄漏）。
- 模型清单按 provider 分组返回；目前 omp 默认 provider 名为
  `cloud-ai`，但实现按文件中所有 providers 通用处理。
"""

from __future__ import annotations

import os
import pathlib
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException

from app.utils.logging import get_logger

router = APIRouter(prefix="/models/omp", tags=["models-omp"])
logger = get_logger(__name__)


_OMP_MODELS_FILE = pathlib.Path.home() / ".omp" / "agent" / "models.yml"


def _resolve_api_key(spec: Any) -> tuple[str | None, bool]:
    """omp 把 apiKey 字段写成环境变量名（约定俗成），但有的工具直接填裸 key。

    Returns:
        (env_var_name, has_value)
        - env_var_name: 当 spec 看起来像环境变量名时返回该名字；否则 None
        - has_value:    无论是环境变量还是裸 key，最终能解析出非空字符串
    """
    if not spec or not isinstance(spec, str):
        return None, False

    # 启发式：环境变量名通常是 [A-Z_][A-Z0-9_]*；裸 key 通常包含小写或连字符
    looks_like_env = spec.replace("_", "").isalnum() and spec.isupper()
    if looks_like_env:
        return spec, bool(os.getenv(spec))
    # 裸 key —— 不暴露具体值，只回报有无
    return None, bool(spec.strip())


@router.get("/catalog")
async def get_omp_catalog() -> dict[str, Any]:
    """读取 ~/.omp/agent/models.yml，列出所有 provider 与模型。

    Response shape::

        {
          "available": true,
          "path": "/Users/.../.omp/agent/models.yml",
          "providers": [
            {
              "id": "cloud-ai",
              "base_url": "http://152.136.41.186:30131/v1",
              "api_key_env": "ONE_HUB_API_KEY",
              "api_key_available": true,
              "models": [
                {"id": "gpt-5", "name": "gpt 5"},
                ...
              ]
            }
          ]
        }
    """
    if not _OMP_MODELS_FILE.exists():
        return {
            "available": False,
            "path": str(_OMP_MODELS_FILE),
            "reason": "omp models config not found on this host",
            "providers": [],
        }

    try:
        with _OMP_MODELS_FILE.open("r", encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        logger.error("Failed to parse omp models.yml: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to parse omp models.yml: {e}") from e

    raw_providers = doc.get("providers") or {}
    if not isinstance(raw_providers, dict):
        raise HTTPException(status_code=500, detail="omp models.yml: 'providers' must be a mapping")

    providers: list[dict[str, Any]] = []
    for provider_id, spec in raw_providers.items():
        if not isinstance(spec, dict):
            continue
        env_name, key_available = _resolve_api_key(spec.get("apiKey"))
        models: list[dict[str, str]] = []
        for m in spec.get("models") or []:
            if not isinstance(m, dict):
                continue
            mid = m.get("id")
            if not mid:
                continue
            models.append({"id": str(mid), "name": str(m.get("name") or mid)})

        providers.append(
            {
                "id": str(provider_id),
                "base_url": spec.get("baseUrl") or "",
                "api_key_env": env_name,
                "api_key_available": key_available,
                "models": models,
            }
        )

    return {
        "available": True,
        "path": str(_OMP_MODELS_FILE),
        "providers": providers,
    }
