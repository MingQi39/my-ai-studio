"""
配置管理器
读取和保存配置到 JSON 文件
"""
import os
import json
from app.travel.config.defaults import DATA_DIR, Settings


# settings.json 只允许覆盖模型相关配置，其余统一从 .env 读取
JSON_OVERRIDE_FIELDS = ("openai_api_key", "openai_base_url", "model_name", "max_rounds")


def get_settings() -> Settings:
    """
    读取配置，不存在则返回默认值
    """
    settings_file = os.path.join(DATA_DIR, "settings.json")

    # 先读取 .env 默认值
    settings = Settings()

    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    for field in JSON_OVERRIDE_FIELDS:
                        if field in data:
                            setattr(settings, field, data[field])
                return settings
        except Exception:
            # 读取失败，退回 .env 配置
            return settings

    return settings


def save_settings(settings: Settings) -> None:
    """
    保存配置到 JSON 文件
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    settings_file = os.path.join(DATA_DIR, "settings.json")

    payload = {field: getattr(settings, field) for field in JSON_OVERRIDE_FIELDS}
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
