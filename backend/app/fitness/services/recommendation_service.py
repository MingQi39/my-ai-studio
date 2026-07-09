"""Meal recommendation for Fitness Agent (v1).

Heuristic recommendation based on:
- target_kcal (budget/remaining)
- meal_type (breakfast/lunch/dinner/snack)
- simple preference keywords (low_oil/vegetarian/cheap/convenient)

For now v1 only guarantees candidates are built from local food library.
Calories are still returned with `source=local`.
"""

from __future__ import annotations

from typing import Literal

from app.fitness.schemas import (
    MealRecommendation,
    MealRecommendationItem,
    Preference,
    ResolvedFoodItem,
)
from app.fitness.services.local_food_db import build_local_index, load_local_foods, resolve_local_food


PreferenceFit = list[str]


def _is_vegetarian(name: str) -> bool:
    # v1 heuristic: allow tofu/egg/veg. Block known meat/fish keywords.
    block = ["牛肉", "猪", "羊", "鸡腿", "鸡", "鱼", "虾", "鸭", "汉堡", "披萨", "炸鸡"]
    return not any(k in name for k in block)


def _is_low_oil(name: str) -> bool:
    block = ["红烧肉", "糖醋排骨", "麻辣香锅", "火锅", "宫保鸡丁", "炸鸡", "油条", "煎鸡蛋", "煎饼果子"]
    return not any(k in name for k in block)


def _scale_to_target(items: list[ResolvedFoodItem], *, carb_index: int, target_kcal: float) -> None:
    total = sum(i.kcal for i in items)
    if total <= 0:
        return
    carb = items[carb_index]
    # linear scaling by kcal
    ratio = target_kcal / total
    new_qty = carb.qty * ratio
    if new_qty <= 0:
        return
    # adjust kcal proportionally (base model assumes kcal scales with qty)
    carb.qty = round(new_qty, 3)  # type: ignore[misc]
    carb.kcal = round(carb.kcal * ratio, 1)  # type: ignore[misc]


def recommend_meals_local(
    *,
    meal_type: str,
    target_kcal: float,
    budget_kcal: float | None = None,
    preferences: list[Preference] | None = None,
) -> list[MealRecommendation]:
    preferences = preferences or []

    local_index = build_local_index()

    # candidate sets
    carb_candidates = ["白米饭", "糙米饭", "面条", "馒头", "燕麦片", "全麦面包", "意大利面", "薯条"]
    protein_candidates = ["番茄炒蛋", "蒸蛋", "鸡胸肉", "清蒸鱼", "虾仁", "麻婆豆腐", "豆腐脑", "沙拉"]
    veggie_candidates = ["蒜蓉西兰花", "清炒小白菜", "凉拌黄瓜", "红烧茄子", "水煮青菜"]
    snack_candidates = ["苹果", "香蕉", "酸奶", "可乐", "半瓶可乐", "绿茶", "拿铁", "豆浆"]

    carb_candidates = [c for c in carb_candidates if resolve_local_food(c) is not None]
    protein_candidates = [p for p in protein_candidates if resolve_local_food(p) is not None]
    veggie_candidates = [v for v in veggie_candidates if resolve_local_food(v) is not None]
    snack_candidates = [s for s in snack_candidates if resolve_local_food(s) is not None]

    # preference filters (v1)
    if "vegetarian" in preferences:
        protein_candidates = [p for p in protein_candidates if _is_vegetarian(p)]
    if "low_oil" in preferences:
        protein_candidates = [p for p in protein_candidates if _is_low_oil(p)]

    target = float(budget_kcal or target_kcal)
    target = max(100, target)

    meal_key = meal_type.strip().lower()
    titles = {
        "breakfast": ["清爽早餐组合", "能量早餐组合", "低油轻食早餐"],
        "lunch": ["午餐均衡组合", "满足感午餐组合", "低油轻食午餐"],
        "dinner": ["晚餐轻量组合", "减脂晚餐组合", "饱腹晚餐组合"],
        "snack": ["加餐轻食", "饱腹加餐", "低油加餐"],
    }
    title_list = titles.get(meal_key, ["健康组合", "均衡组合", "减脂组合"])

    candidates: list[MealRecommendation] = []

    # 3 candidates with different ingredient choices
    bundles = [
        (carb_candidates[:1], protein_candidates[:1], veggie_candidates[:1], None),
        (carb_candidates[1:2] or carb_candidates[:1], protein_candidates[1:2] or protein_candidates[:1], veggie_candidates[1:2] or veggie_candidates[:1], None),
        (carb_candidates[2:3] or carb_candidates[:1], protein_candidates[2:3] or protein_candidates[:1], veggie_candidates[2:3] or veggie_candidates[:1], snack_candidates[:1]),
    ]

    for idx, (carbs, proteins, vegs, snack) in enumerate(bundles[:3], start=1):
        items: list[ResolvedFoodItem] = []
        carb_name = carbs[0]
        protein_name = proteins[0] if proteins else carbs[0]
        veg_name = vegs[0] if vegs else carbs[0]
        local_c = resolve_local_food(carb_name)
        local_p = resolve_local_food(protein_name)
        local_v = resolve_local_food(veg_name)
        if not local_c or not local_p or not local_v:
            continue

        items.append(
            ResolvedFoodItem(
                name=local_c.name,
                qty=1.0,
                unit=local_c.unit,
                kcal=round(local_c.kcal, 1),
                source="local",
                assumed=False,
            )
        )
        items.append(
            ResolvedFoodItem(
                name=local_p.name,
                qty=1.0,
                unit=local_p.unit,
                kcal=round(local_p.kcal, 1),
                source="local",
                assumed=False,
            )
        )
        items.append(
            ResolvedFoodItem(
                name=local_v.name,
                qty=1.0,
                unit=local_v.unit,
                kcal=round(local_v.kcal, 1),
                source="local",
                assumed=False,
            )
        )
        carb_index = 0
        _scale_to_target(items, carb_index=carb_index, target_kcal=target)

        rec_items = [
            MealRecommendationItem(
                name=i.name,
                qty=i.qty,
                unit=i.unit,
                kcal=i.kcal,
                source=i.source,  # type: ignore[arg-type]
            )
            for i in items
        ]

        if snack:
            snack_name = snack[0]
            local_s = resolve_local_food(snack_name)
            if local_s:
                rec_items.append(
                    MealRecommendationItem(
                        name=local_s.name,
                        qty=1.0,
                        unit=local_s.unit,
                        kcal=round(local_s.kcal, 1),
                        source="local",
                    )
                )

        total = round(sum(i.kcal for i in rec_items), 1)
        candidates.append(
            MealRecommendation(
                id=f"rec-{idx}",
                title=title_list[idx - 1] if idx - 1 < len(title_list) else f"候选{idx}",
                items=rec_items,
                total_kcal=total,
                preference_fit=[*preferences],
                notes=None,
            )
        )

    # fallback: if filters removed everything
    if not candidates:
        # take the first possible local carb+protein+veg
        carb_name = carb_candidates[0] if carb_candidates else None
        protein_name = protein_candidates[0] if protein_candidates else carb_name
        veg_name = veggie_candidates[0] if veggie_candidates else carb_name
        if carb_name and protein_name and veg_name:
            local_c = resolve_local_food(carb_name)
            local_p = resolve_local_food(protein_name)
            local_v = resolve_local_food(veg_name)
            if local_c and local_p and local_v:
                items = [
                    MealRecommendationItem(
                        name=local_c.name,
                        qty=1.0,
                        unit=local_c.unit,
                        kcal=round(local_c.kcal, 1),
                        source="local",
                    ),
                    MealRecommendationItem(
                        name=local_p.name,
                        qty=1.0,
                        unit=local_p.unit,
                        kcal=round(local_p.kcal, 1),
                        source="local",
                    ),
                    MealRecommendationItem(
                        name=local_v.name,
                        qty=1.0,
                        unit=local_v.unit,
                        kcal=round(local_v.kcal, 1),
                        source="local",
                    ),
                ]
                total = round(sum(i.kcal for i in items), 1)
                candidates.append(
                    MealRecommendation(
                        id="rec-1",
                        title="健康组合",
                        items=items,
                        total_kcal=total,
                        preference_fit=preferences,
                        notes=None,
                    )
                )

    return candidates[:3]

