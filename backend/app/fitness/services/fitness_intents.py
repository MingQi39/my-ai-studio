"""Lightweight intent helpers for Fitness Agent direct tool routing."""

from __future__ import annotations

import re

GOAL_KCAL_PATTERNS = (
    re.compile(
        r"(?:设为|设置为|改成|改为|调整到?|设成|更新为)\s*(\d{3,5})\s*(?:kcal|大卡|千卡|卡)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(\d{3,5})\s*(?:kcal|大卡|千卡).{0,12}(?:目标|热量)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:目标|热量|卡路里).{0,20}(?:设为|设置为|改成|改为|调整到?|设成|更新为)\s*(\d{3,5})",
        re.IGNORECASE,
    ),
)

GOAL_UPDATE_HINTS = ("目标", "热量", "卡路里", "kcal", "大卡", "千卡")
GOAL_UPDATE_ACTIONS = ("设", "改", "调整", "更新", "换成", "变为")

RECOMMEND_HINTS = ("推荐", "吃什么", "吃啥", "搭配", "套餐", "食谱")
MEAL_LOG_EXPLICIT = ("记录", "帮我记", "记一下", "记账", "我想记录", "入账")
MEAL_LOG_QUERY_HINTS = ("还剩", "剩余", "多少卡", "查询", "总结", "统计")
MEAL_TYPE_HINTS: dict[str, tuple[str, ...]] = {
    "breakfast": ("早饭", "早餐", "早上"),
    "lunch": ("午饭", "午餐", "中午"),
    "dinner": ("晚饭", "晚餐", "晚上"),
    "snack": ("加餐", "零食", "宵夜"),
}


def is_low_signal_message(message: str) -> bool:
    """Detect short/noisy follow-ups that should not trigger free-form agent answers."""
    text = (message or "").strip()
    if not text:
        return True
    lowered = text.lower()
    if lowered in {"ok", "okay", "k", "kk", "g", "嗯", "哦", "好", "好的", "收到"}:
        return True
    if len(text) <= 2 and re.fullmatch(r"[a-zA-Z0-9]+", text):
        return True
    return False


def extract_goal_kcal(message: str) -> int | None:
    text = (message or "").strip()
    if not text:
        return None
    for pattern in GOAL_KCAL_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        value = int(match.group(1))
        if 800 <= value <= 10000:
            return value
    return None


def is_goal_update_request(message: str) -> bool:
    if extract_goal_kcal(message) is None:
        return False
    text = message or ""
    return any(hint in text for hint in GOAL_UPDATE_HINTS) and any(
        action in text for action in GOAL_UPDATE_ACTIONS
    )


def is_recommendation_request(message: str) -> bool:
    text = message or ""
    return any(hint in text for hint in RECOMMEND_HINTS)


def is_meal_log_request(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if is_goal_update_request(text) or is_recommendation_request(text):
        return False
    if "我想记录" in text and "吃了" in text:
        return True
    if any(hint in text for hint in MEAL_LOG_QUERY_HINTS) and "吃" not in text:
        return False
    if text.startswith(("删", "取消")) or "删除" in text:
        return False
    if any(hint in text for hint in MEAL_LOG_EXPLICIT):
        return True
    ate_food = "吃" in text or "喝了" in text
    has_meal_time = any(hint in text for hints in MEAL_TYPE_HINTS.values() for hint in hints)
    has_food_like = any(
        token in text
        for token in ("饭", "面", "菜", "肉", "蛋", "奶", "果", "饼", "戟", "餐", "筋", "零食", "肠", "干", "包")
    )
    return ate_food and (has_meal_time or has_food_like)


def detect_meal_type(message: str, default: str = "dinner") -> str:
    text = message or ""
    for meal_type, hints in MEAL_TYPE_HINTS.items():
        if any(hint in text for hint in hints):
            return meal_type
    return default
