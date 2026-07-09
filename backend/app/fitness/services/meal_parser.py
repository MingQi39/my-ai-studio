"""Parse meal foods from natural language user messages."""

from __future__ import annotations

import json
import re
from typing import Any

from app.fitness.schemas import FoodItemInput
from app.fitness.services.local_food_db import normalize_food_name

_QTY_WORDS = {"一": 1, "半": 0.5, "两": 2, "俩": 2, "几": 1}
_UNITS = "个包碗份杯瓶块根片袋盒串只"
_ITEM_RE = re.compile(rf"^(?:(?P<qty_word>[一二半两俩几]))?(?:(?P<unit>[{_UNITS}]))?(?P<name>.+)$")
_GRAM_SUFFIX_RE = re.compile(r"^(?P<name>.+?)(?P<qty>\d+(?:\.\d+)?)\s*(?:g|G|克|kg|KG|千克|公斤)$")
_MEAL_PREFIX_RE = re.compile(
    r"^(?:早上|上午|中午|下午|晚上|早饭|早餐|午饭|午餐|晚饭|晚餐|加餐|零食)[，,、\s]*",
)
_LEADING_VERB_RE = re.compile(r"^(?:我)?(?:还)?(?:想)?吃了?|喝了?")


def extract_foods_heuristic(message: str) -> list[FoodItemInput]:
    """Best-effort food extraction without LLM (fallback)."""
    text = (message or "").strip()
    if not text:
        return []

    if "吃了" in text:
        text = re.split(r"吃了[：:]?", text, maxsplit=1)[-1].strip()
    text = _MEAL_PREFIX_RE.sub("", text)
    text = _LEADING_VERB_RE.sub("", text).strip(" ，,、")
    text = text.split("。")[0].split("，请")[0].strip()
    if not text:
        return []

    chunks = [part.strip() for part in re.split(r"[、,，;；\n]+", text) if part.strip()]
    if not chunks:
        chunks = [text]

    foods: list[FoodItemInput] = []
    for chunk in chunks:
        parsed = _parse_food_chunk(chunk)
        if parsed is not None:
            foods.append(parsed)
    return foods


def _parse_gram_suffix(chunk: str) -> FoodItemInput | None:
    """Parse trailing weight like 上脑皇250g / 鸡胸肉 100克."""
    match = _GRAM_SUFFIX_RE.match(chunk.strip())
    if not match:
        return None
    name = normalize_food_name((match.group("name") or "").strip())
    if not name:
        return None
    qty_text = match.group("qty") or "0"
    qty = float(qty_text)
    if qty <= 0:
        return None
    unit = "克"
    if chunk.strip().lower().endswith(("kg", "千克", "公斤")):
        qty *= 1000
    return FoodItemInput(name=name, qty=qty, unit=unit)


def _parse_food_chunk(chunk: str) -> FoodItemInput | None:
    chunk = chunk.strip()
    if len(chunk) < 2:
        return None

    gram_parsed = _parse_gram_suffix(chunk)
    if gram_parsed is not None:
        return gram_parsed

    match = _ITEM_RE.match(chunk)
    if not match:
        return FoodItemInput(name=chunk, qty=1.0, unit="份")

    qty_word = match.group("qty_word")
    unit = match.group("unit") or "份"
    name = (match.group("name") or "").strip()
    if not name:
        return None
    qty = float(_QTY_WORDS.get(qty_word, 1)) if qty_word else 1.0
    return FoodItemInput(name=normalize_food_name(name), qty=qty, unit=unit)


async def parse_meal_foods_from_message(
    message: str,
    *,
    openai_client: Any,
    model_name: str,
) -> list[FoodItemInput]:
    """Extract structured food items from a meal-logging utterance."""
    text = (message or "").strip()
    if not text:
        return []

    heuristic = extract_foods_heuristic(text)
    if heuristic:
        return heuristic

    system = (
        "你是饮食记录助手。从用户消息中提取实际吃到的食物列表。"
        "输出严格 JSON：{\"foods\": [{\"name\": \"食物名\", \"qty\": 数量, \"unit\": \"单位\"}]}。"
        "规则：\n"
        "- 只提取用户明确吃到的食物，忽略推荐/询问类内容\n"
        "- 未说明份量时合理假设（如「一个香蕉」→ qty=1, unit=个）\n"
        "- 品牌名并入 name（如「山姆芒果班戟」）\n"
        "- foods 至少 1 项；无法识别时返回 {\"foods\": []}"
    )
    user = f"用户消息：{text}"

    try:
        resp = await openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        parsed = json.loads(content)
    except Exception:
        return extract_foods_heuristic(text)

    foods_raw = parsed.get("foods") or []
    foods: list[FoodItemInput] = []
    for item in foods_raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        try:
            qty = float(item.get("qty") or 1)
        except (TypeError, ValueError):
            qty = 1.0
        unit = str(item.get("unit") or "份").strip() or "份"
        foods.append(FoodItemInput(name=normalize_food_name(name), qty=qty, unit=unit))

    return foods or extract_foods_heuristic(text)
