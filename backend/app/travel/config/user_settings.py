"""Per-user travel agent preferences (max_rounds, etc.)."""

import json
import os
from uuid import UUID

from app.travel.config.defaults import Settings


def _user_settings_path(user_id: UUID) -> str:
    base = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "data",
        "travel",
        str(user_id),
    )
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "settings.json")


def get_user_travel_settings(user_id: UUID) -> Settings:
    settings = Settings()
    path = _user_settings_path(user_id)
    if not os.path.exists(path):
        return settings

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "max_rounds" in data:
            settings.max_rounds = int(data["max_rounds"])
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass

    return settings


def save_user_travel_settings(user_id: UUID, max_rounds: int) -> None:
    path = _user_settings_path(user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"max_rounds": max_rounds}, f, indent=2, ensure_ascii=False)
