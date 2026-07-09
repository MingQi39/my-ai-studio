"""Timezone helpers for Fitness Agent."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import settings


def resolve_timezone(name: str | None = None) -> ZoneInfo:
    tz_name = name or settings.FITNESS_DEFAULT_TIMEZONE
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Asia/Shanghai")


def today_for_timezone(name: str | None = None) -> date:
    return datetime.now(resolve_timezone(name)).date()
