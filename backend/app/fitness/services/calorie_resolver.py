"""Calorie resolution chain for Fitness Agent.

Chain:
1) local (自建小库) → LLM 校验（可疑或模糊命中时）
2) USDA (可选，USDA_FDC_API_KEY) → LLM 校验
3) web search (可选，TAVILY_API_KEY) → LLM 从摘要提取热量
4) LLM estimate (兜底，source=estimate)
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.config import settings
from app.fitness.schemas import FoodItemInput, ResolvedFoodItem
from app.fitness.services.local_food_db import (
    is_exact_local_match,
    normalize_food_name,
    resolve_local_food,
)
from app.travel.services.tavily_client import TavilyClient


logger = logging.getLogger(__name__)

CalorieSource = Literal["local", "usda", "web", "estimate"]
ProgressCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


async def _emit_progress(
    callback: ProgressCallback | None,
    stage: str,
    **detail: Any,
) -> None:
    if callback:
        await callback(stage, detail)

_LLM_ESTIMATE_SYSTEM = (
    "你是营养热量估算助手。根据食物名称、份量、单位，估算总热量（kcal）。"
    "输出严格 JSON：kcal（数字）、assumed（布尔）、food_category（字符串，如肉类/主食/蔬菜）。"
    "规则：\n"
    "- 先理解食物本质：中文菜名、品牌名、部位名（如上脑/眼肉/西冷/肋排/肥牛）、"
    "烹饪方式（烤/炸/蒸）都要纳入判断。「上脑皇」等含部位或肉类暗示的名称应识别为牛肉类\n"
    "- kcal 为 qty/unit 的总热量，不是每 100g\n"
    "- 单位为克/公斤时：按每 100g 密度换算，熟牛肉约 200–320 kcal/100g，"
    "烤排骨约 250–350 kcal/100g，蔬菜约 15–50 kcal/100g\n"
    "- 单位为份/个/碗时：按常见一份估算，通常 50–800 kcal\n"
    "- kcal 必须为正数"
)


_WEIGHT_UNITS_G = frozenset({"克", "g", "gram", "grams"})
_WEIGHT_UNITS_KG = frozenset({"公斤", "kg", "kilogram", "kilograms"})


def _is_weight_unit(unit: str) -> bool:
    u = unit.strip().lower()
    return u in _WEIGHT_UNITS_G or u in _WEIGHT_UNITS_KG or unit.strip() in {"克", "公斤"}


def _qty_to_grams(qty: float, unit: str) -> float:
    u = unit.strip().lower()
    if u in _WEIGHT_UNITS_KG or unit.strip() == "公斤":
        return float(qty) * 1000.0
    return float(qty)


def _kcal_per_100g_for_food(food_name: str) -> float:
    """Heuristic kcal density (per 100g) for weight-based fallback."""
    dessert_kw = ("班戟", "蛋糕", "甜点", "甜品", "披萨", "可颂", "泡芙", "布丁", "冰激凌", "冰淇淋")
    snack_kw = ("筋", "肉干", "零食", "薯片", "饼干", "巧克力", "坚果")
    meat_kw = (
        "肉", "牛", "羊", "猪", "鸡", "鸭", "排骨", "鱼", "虾", "蟹",
        "培根", "火腿", "上脑", "里脊", "肥牛", "牛排", "肋", "扒",
    )
    staple_kw = ("饭", "面", "粉", "粥", "馒头", "包子", "饺子")
    veg_kw = ("菜", "蔬", "瓜", "茄", "菇", "笋", "豆", "西兰花", "白菜")
    if any(k in food_name for k in dessert_kw):
        return 350.0
    if any(k in food_name for k in snack_kw):
        return 450.0
    if any(k in food_name for k in meat_kw):
        return 250.0
    if any(k in food_name for k in staple_kw):
        return 130.0
    if any(k in food_name for k in veg_kw):
        return 35.0
    return 150.0


def _kcal_per_serving_for_food(food_name: str) -> float:
    """Heuristic kcal per discrete serving (份/个/碗等)."""
    dessert_kw = ("班戟", "蛋糕", "甜点", "甜品", "披萨", "可颂", "泡芙", "布丁", "冰激凌", "冰淇淋")
    snack_kw = ("筋", "肉干", "零食", "薯片", "饼干", "巧克力", "坚果")
    if any(k in food_name for k in dessert_kw):
        return 220.0
    if any(k in food_name for k in snack_kw):
        return 120.0
    if any(k in food_name for k in ("饭", "面", "粉")):
        return 400.0
    return 150.0


def _fallback_estimate_kcal(food_name: str, qty: float, unit: str) -> float:
    """Category-based fallback when LLM returns invalid (e.g. 0) kcal."""
    if _is_weight_unit(unit):
        grams = _qty_to_grams(qty, unit)
        per_100g = _kcal_per_100g_for_food(food_name)
        return round(per_100g * (grams / 100.0), 1)
    return round(_kcal_per_serving_for_food(food_name) * float(qty), 1)


_BEVERAGE_KEYWORDS = ("咖啡", "茶", "水", "可乐", "汽水", "饮料", "汁")


def _is_beverage_like(food_name: str) -> bool:
    return any(k in food_name for k in _BEVERAGE_KEYWORDS)


def _is_kcal_suspicious(*, food_name: str, qty: float, unit: str, kcal: float) -> bool:
    """Fast heuristic before LLM validation for API-sourced kcal."""
    if kcal <= 0:
        return True
    if kcal < 15 and not _is_beverage_like(food_name):
        return True
    if kcal > 2500:
        return True

    unit_norm = unit.strip().lower()
    if unit_norm in {"克", "g", "gram", "grams"} and qty > 0:
        per_g = kcal / qty
        if per_g < 0.2 or per_g > 9.5:
            return True
    return False


def _apply_kcal_sanity_fallback(item: ResolvedFoodItem, *, reason: str) -> ResolvedFoodItem:
    """Sync keyword fallback — prefer async LLM correction when client is available."""
    if not _is_kcal_suspicious(
        food_name=item.name, qty=item.qty, unit=item.unit, kcal=item.kcal
    ):
        return item
    corrected = _fallback_estimate_kcal(item.name, item.qty, item.unit)
    return ResolvedFoodItem(
        name=item.name,
        qty=item.qty,
        unit=item.unit,
        kcal=corrected,
        source="estimate",
        assumed=True,
        note=f"{reason}；已按份量经验值修正",
    )


async def _llm_reestimate_kcal(
    *,
    openai_client: Any,
    model_name: str,
    food_name: str,
    qty: float,
    unit: str,
    context: str | None = None,
) -> float | None:
    """Ask LLM to re-estimate when a prior value was implausible."""
    user_lines = [f"食物：{food_name}", f"份量：{qty}", f"单位：{unit}", "请估算总热量 kcal。"]
    if context:
        user_lines.insert(0, f"背景：{context}")
    try:
        resp = await openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": _LLM_ESTIMATE_SYSTEM},
                {"role": "user", "content": "\n".join(user_lines)},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(resp.choices[0].message.content or "{}")
    except Exception as exc:
        logger.info("Fitness LLM re-estimate failed for %s: %s", food_name, exc)
        return None

    kcal = float(parsed.get("kcal") or 0)
    if kcal <= 0 or _is_kcal_suspicious(
        food_name=food_name, qty=qty, unit=unit, kcal=kcal
    ):
        return None
    return round(kcal, 1)


async def _correct_implausible_kcal(
    *,
    openai_client: Any,
    model_name: str,
    item: ResolvedFoodItem,
    reason: str,
    context: str | None = None,
) -> ResolvedFoodItem:
    """Prefer LLM semantic re-estimate; keyword fallback only if LLM unavailable."""
    if not _is_kcal_suspicious(
        food_name=item.name, qty=item.qty, unit=item.unit, kcal=item.kcal
    ):
        return item

    corrected = await _llm_reestimate_kcal(
        openai_client=openai_client,
        model_name=model_name,
        food_name=item.name,
        qty=item.qty,
        unit=item.unit,
        context=context or f"{reason}，先前值 {item.kcal} kcal 不合理",
    )
    if corrected is not None:
        return ResolvedFoodItem(
            name=item.name,
            qty=item.qty,
            unit=item.unit,
            kcal=corrected,
            source="estimate",
            assumed=True,
            note=f"{reason}；已由 LLM 重新估算",
        )

    return _apply_kcal_sanity_fallback(item, reason=reason)


def _should_validate_api_kcal(
    *,
    food_name: str,
    qty: float,
    unit: str,
    kcal: float,
    source: CalorieSource,
    exact_local_match: bool,
) -> bool:
    if source not in {"local", "usda"}:
        return False
    if source == "usda":
        return True
    if _is_kcal_suspicious(food_name=food_name, qty=qty, unit=unit, kcal=kcal):
        return True
    # Substring local hits are more error-prone than exact name/alias matches.
    return not exact_local_match


async def _validate_api_kcal_with_llm(
    *,
    openai_client: Any,
    model_name: str,
    item: ResolvedFoodItem,
    lookup_name: str | None = None,
) -> ResolvedFoodItem:
    """LLM sanity-check for local/USDA kcal; correct when implausible."""
    source_label = {"local": "本地库", "usda": "USDA"}.get(item.source, item.source)
    lookup = lookup_name or item.name
    system = (
        "你是营养热量校验助手。根据食物名称、份量、单位，判断接口返回的热量是否合理。"
        "输出严格 JSON：plausible（布尔）、kcal（数字）、reason（字符串，简短中文）。"
        "规则：\n"
        "- 先理解食物本质：中文部位名（上脑/眼肉/肋排）、品牌修饰（如上脑皇）通常指牛肉/肉类\n"
        "- kcal 为 qty/unit 的总热量，不是每 100g\n"
        "- 单位为克时：熟肉约 2–3.5 kcal/g，蔬菜约 0.15–0.5 kcal/g\n"
        "- 常见一份固体食物通常 30–1200 kcal；饮料可低至 0–50 kcal\n"
        "- 肉类/主食若只有 1–10 kcal 通常不合理\n"
        "- plausible=true 时 kcal 应等于接口值；plausible=false 时给出合理修正值\n"
        "- 修正值必须为正数，需结合食物类别与份量语义估算"
    )
    user = (
        f"食物：{item.name}\n份量：{item.qty}\n单位：{item.unit}\n"
        f"接口来源：{source_label}\n匹配条目：{lookup}\n"
        f"接口热量：{item.kcal} kcal\n"
        "请校验该热量是否合理。"
    )

    try:
        resp = await openai_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        parsed = json.loads(content)
    except Exception as exc:
        logger.info("Fitness API kcal validation failed for %s: %s", item.name, exc)
        return item

    plausible = bool(parsed.get("plausible"))
    if plausible:
        return item

    corrected = float(parsed.get("kcal") or 0)
    reason = str(parsed.get("reason") or "").strip()
    if corrected <= 0 or _is_kcal_suspicious(
        food_name=item.name, qty=item.qty, unit=item.unit, kcal=corrected
    ):
        reestimated = await _llm_reestimate_kcal(
            openai_client=openai_client,
            model_name=model_name,
            food_name=item.name,
            qty=item.qty,
            unit=item.unit,
            context=f"{source_label} 校验未通过（{reason or '接口值不合理'}）",
        )
        if reestimated is not None:
            corrected = reestimated
        else:
            corrected = _fallback_estimate_kcal(item.name, item.qty, item.unit)

    note_parts = [f"{source_label} 数据已校验修正"]
    if reason:
        note_parts.append(reason)
    return ResolvedFoodItem(
        name=item.name,
        qty=item.qty,
        unit=item.unit,
        kcal=round(corrected, 1),
        source="estimate",
        assumed=True,
        note="；".join(note_parts),
    )


def _format_search_snippets(results: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for index, item in enumerate(results, start=1):
        title = str(item.get("title") or "").strip()
        content = str(item.get("content") or "").strip()
        if not title and not content:
            continue
        parts.append(f"[{index}] {title}\n{content}".strip())
    return "\n\n".join(parts)


def _build_food_calorie_search_query(food_name: str, qty: float, unit: str) -> str:
    qty_text = f"{qty:g}{unit}" if qty != 1 else unit
    return f"{food_name} {qty_text} 热量 卡路里 kcal"


async def _extract_kcal_from_search_snippets(
    *,
    openai_client: Any,
    model_name: str,
    food_name: str,
    qty: float,
    unit: str,
    snippets: str,
) -> tuple[float, bool, bool]:
    """Use LLM to extract kcal from web search snippets. Returns (kcal, found, assumed)."""
    system = (
        "你是营养数据提取助手。根据联网搜索摘要，判断是否能找到该食物热量的可靠依据，"
        "并换算为用户指定份量的总热量（kcal）。"
        "输出严格 JSON：found（布尔）、kcal（数字，found=false 时为 0）、assumed（布尔）。"
        "规则：\n"
        "- kcal 为 qty/unit 的总热量，不是每 100g\n"
        "- 摘要只有每 100g 时请合理换算\n"
        "- 找不到可靠数据时 found=false，不要编造\n"
        "- found=true 时 kcal 必须为正数"
    )
    user = (
        f"食物：{food_name}\n份量：{qty}\n单位：{unit}\n\n"
        f"搜索摘要：\n{snippets}\n\n"
        "请提取总热量。"
    )

    resp = await openai_client.chat.completions.create(
        model=model_name,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or "{}"
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return 0.0, False, True

    found = bool(parsed.get("found"))
    kcal = float(parsed.get("kcal") or 0)
    assumed = bool(parsed.get("assumed")) if "assumed" in parsed else True
    if not found or kcal <= 0:
        return 0.0, False, assumed
    return kcal, True, assumed


async def _resolve_calories_web_search(
    *,
    food_name: str,
    qty: float,
    unit: str,
    tavily_api_key: str,
    openai_client: Any,
    model_name: str,
    http_timeout_seconds: int,
    max_results: int,
    on_progress: ProgressCallback | None = None,
) -> ResolvedFoodItem | None:
    """Search the web (Tavily) and extract kcal from snippets via LLM."""
    client = TavilyClient(
        tavily_api_key,
        timeout=http_timeout_seconds,
        max_results=max_results,
    )
    query = _build_food_calorie_search_query(food_name, qty, unit)
    try:
        results = await client.search(query)
    except Exception as exc:
        logger.info("Fitness web calorie search failed for %s: %s", food_name, exc)
        return None

    snippets = _format_search_snippets(results)
    if not snippets:
        return None

    await _emit_progress(on_progress, "web_extract", food_name=food_name)

    kcal, found, assumed = await _extract_kcal_from_search_snippets(
        openai_client=openai_client,
        model_name=model_name,
        food_name=food_name,
        qty=qty,
        unit=unit,
        snippets=snippets,
    )
    if not found:
        return None

    item = ResolvedFoodItem(
        name=food_name,
        qty=qty,
        unit=unit,
        kcal=round(kcal, 1),
        source="web",
        assumed=assumed,
        note="联网搜索参考（仅供参考）",
    )
    return await _correct_implausible_kcal(
        openai_client=openai_client,
        model_name=model_name,
        item=item,
        reason="联网搜索热量偏离合理范围",
    )


@dataclass(frozen=True)
class USDAResolved:
    kcal_per_base_qty: float
    base_qty: float


async def _estimate_calories_llm(
    *,
    openai_client: Any,
    model_name: str,
    food_name: str,
    qty: float,
    unit: str,
) -> ResolvedFoodItem:
    """LLM estimate: 输出 kcal + source=estimate."""
    user = f"食物：{food_name}\n份量：{qty}\n单位：{unit}\n请估算总热量 kcal。"

    resp = await openai_client.chat.completions.create(
        model=model_name,
        messages=[{"role": "system", "content": _LLM_ESTIMATE_SYSTEM}, {"role": "user", "content": user}],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    msg = resp.choices[0].message
    content = msg.content or "{}"
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = {}

    kcal = float(parsed.get("kcal") or 0)
    assumed = bool(parsed.get("assumed")) if "assumed" in parsed else True
    note = "LLM 估算（仅供参考）"
    if kcal <= 0:
        kcal = _fallback_estimate_kcal(food_name, qty, unit)
        note = "LLM 估算无效，已用经验值兜底"
    item = ResolvedFoodItem(
        name=food_name,
        qty=qty,
        unit=unit,
        kcal=kcal,
        source="estimate",
        assumed=assumed,
        note=note,
    )
    return await _correct_implausible_kcal(
        openai_client=openai_client,
        model_name=model_name,
        item=item,
        reason="LLM 估算偏离合理范围",
    )


async def _resolve_usda_energy_kcal_per_serving(
    *,
    food_name: str,
    api_key: str,
    http_timeout_seconds: int,
) -> USDAResolved | None:
    """Best-effort USDA lookup.

    We try to search food candidates and extract Energy nutrient (kcal).
    If anything fails, return None (let caller fallback to estimate).
    """
    url = "https://api.nal.usda.gov/fdc/v1/foods/search"
    params = {
        "api_key": api_key,
        "query": food_name,
        "pageSize": 1,
    }
    async with httpx.AsyncClient(timeout=http_timeout_seconds) as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            return None
        data = resp.json()

    foods = data.get("foods") or []
    if not foods:
        return None

    food = foods[0]
    nutrients = food.get("foodNutrients") or []
    energy = None
    for n in nutrients:
        # common patterns: nutrientName / unitName
        if str(n.get("nutrientName") or "").lower() == "energy":
            energy = n
            break
        if str(n.get("nutrientId") or "") == "1008":  # Energy, kcal
            energy = n
            break
    if not energy:
        return None

    kcal = energy.get("value")
    if kcal is None:
        return None

    # Serving/base_qty: if serving size unknown, treat as base_qty=1.
    base_qty = 1.0
    # If servingSize is present and numeric, we still can't convert units reliably,
    # but we can at least set base_qty to servingQty.
    serving_qty = food.get("servingSize") or food.get("servingQty")
    if isinstance(serving_qty, (int, float)) and serving_qty > 0:
        base_qty = float(serving_qty)

    return USDAResolved(kcal_per_base_qty=float(kcal), base_qty=base_qty)


async def resolve_food_calories(
    foods: list[FoodItemInput],
    *,
    openai_client: Any,
    model_name: str,
    usda_api_key: str | None = None,
    tavily_api_key: str | None = None,
    http_timeout_seconds: int | None = None,
    on_progress: ProgressCallback | None = None,
) -> list[ResolvedFoodItem]:
    """Resolve a list of foods to kcal with source tagging."""
    http_timeout_seconds = http_timeout_seconds or settings.HTTP_TIMEOUT_SECONDS
    resolved: list[ResolvedFoodItem] = []
    usda_api_key = usda_api_key or settings.USDA_FDC_API_KEY
    if tavily_api_key is None:
        tavily_api_key = settings.TAVILY_API_KEY

    total = len(foods)
    await _emit_progress(on_progress, "parse_foods", total=total)

    for index, f in enumerate(foods, start=1):
        food_name = normalize_food_name(f.name)
        await _emit_progress(
            on_progress,
            "food_start",
            food_name=food_name,
            index=index,
            total=total,
        )
        # 1) local
        await _emit_progress(on_progress, "local_lookup", food_name=food_name, index=index, total=total)
        local_entry = resolve_local_food(food_name)
        if local_entry is not None:
            if _is_weight_unit(f.unit) and local_entry.grams:
                kcal = local_entry.kcal * (_qty_to_grams(f.qty, f.unit) / float(local_entry.grams))
            else:
                kcal = local_entry.kcal * (float(f.qty) / float(local_entry.qty or 1))
            resolved_item = ResolvedFoodItem(
                name=local_entry.name,
                qty=f.qty,
                unit=f.unit,
                kcal=round(kcal, 1),
                source="local",
                assumed=False,
                note=None,
            )
            if _should_validate_api_kcal(
                food_name=food_name,
                qty=f.qty,
                unit=f.unit,
                kcal=resolved_item.kcal,
                source="local",
                exact_local_match=is_exact_local_match(food_name),
            ):
                await _emit_progress(
                    on_progress,
                    "local_validate",
                    food_name=food_name,
                    index=index,
                    total=total,
                )
                resolved_item = await _validate_api_kcal_with_llm(
                    openai_client=openai_client,
                    model_name=model_name,
                    item=resolved_item,
                    lookup_name=local_entry.name,
                )
            resolved.append(resolved_item)
            continue

        # 2) USDA
        if usda_api_key:
            await _emit_progress(
                on_progress,
                "usda_lookup",
                food_name=food_name,
                index=index,
                total=total,
            )
            try:
                usda = await _resolve_usda_energy_kcal_per_serving(
                    food_name=food_name,
                    api_key=usda_api_key,
                    http_timeout_seconds=http_timeout_seconds,
                )
                if usda is not None:
                    base_qty = float(usda.base_qty or 1)
                    # FDC nutrients are typically per 100g; default base_qty=1 is misleading.
                    if _is_weight_unit(f.unit) and base_qty == 1.0:
                        base_qty = 100.0
                    kcal = usda.kcal_per_base_qty * (float(f.qty) / base_qty)
                    resolved_item = ResolvedFoodItem(
                        name=food_name,
                        qty=f.qty,
                        unit=f.unit,
                        kcal=round(kcal, 1),
                        source="usda",
                        assumed=False,
                        note="USDA FoodData Central 能量估算",
                    )
                    await _emit_progress(
                        on_progress,
                        "usda_validate",
                        food_name=food_name,
                        index=index,
                        total=total,
                    )
                    resolved_item = await _validate_api_kcal_with_llm(
                        openai_client=openai_client,
                        model_name=model_name,
                        item=resolved_item,
                        lookup_name=food_name,
                    )
                    resolved.append(resolved_item)
                    continue
            except Exception:
                # silent fallback to web / estimate
                pass

        # 3) Web search (Tavily) + LLM extract from snippets
        if tavily_api_key:
            await _emit_progress(
                on_progress,
                "web_search",
                food_name=food_name,
                index=index,
                total=total,
            )
            try:
                web = await _resolve_calories_web_search(
                    food_name=food_name,
                    qty=f.qty,
                    unit=f.unit,
                    tavily_api_key=tavily_api_key,
                    openai_client=openai_client,
                    model_name=model_name,
                    http_timeout_seconds=http_timeout_seconds,
                    max_results=settings.TAVILY_MAX_RESULTS,
                    on_progress=on_progress,
                )
                if web is not None:
                    resolved.append(web)
                    continue
            except Exception as exc:
                logger.info("Fitness web calorie resolve failed for %s: %s", food_name, exc)

        # 4) LLM estimate (last resort)
        await _emit_progress(
            on_progress,
            "llm_estimate",
            food_name=food_name,
            index=index,
            total=total,
        )
        resolved.append(
            await _estimate_calories_llm(
                openai_client=openai_client,
                model_name=model_name,
                food_name=food_name,
                qty=f.qty,
                unit=f.unit,
            )
        )

    return resolved

