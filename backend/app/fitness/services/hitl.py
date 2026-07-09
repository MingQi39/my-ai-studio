"""Human-in-the-loop helpers for Fitness Agent write tools."""

from __future__ import annotations

from typing import Any

from app.fitness.schemas import FitnessGoalUpdate
from app.fitness.services.fitness_service import FitnessService

WRITE_TOOLS = frozenset({"log_meal", "set_daily_calorie_goal", "delete_diary_entry"})

MEAL_TYPE_LABELS = {
    "breakfast": "早餐",
    "lunch": "午餐",
    "dinner": "晚餐",
    "snack": "加餐",
}


def is_write_tool(tool_name: str) -> bool:
    return tool_name in WRITE_TOOLS


def build_approval_preview(
    tool_name: str,
    tool_args: dict[str, Any],
    *,
    previous_goal: int | None = None,
) -> dict[str, Any]:
    if tool_name == "set_daily_calorie_goal":
        goal = tool_args.get("daily_calorie_goal")
        if goal is None and "update" in tool_args:
            goal = (tool_args.get("update") or {}).get("daily_calorie_goal")
        return {
            "kind": "set_goal",
            "daily_calorie_goal": int(goal or 0),
            "previous_daily_calorie_goal": previous_goal,
        }

    if tool_name == "log_meal":
        items = tool_args.get("items") or []
        total = round(sum(float(item.get("kcal", 0) or 0) for item in items), 1)
        return {
            "kind": "log_meal",
            "meal_type": str(tool_args.get("meal_type") or "lunch"),
            "items": items,
            "total_kcal": total,
            "note": tool_args.get("note"),
        }

    if tool_name == "delete_diary_entry":
        entry_id = tool_args.get("entry_id")
        return {
            "kind": "delete_entry",
            "entry_id": str(entry_id or ""),
        }

    return {
        "kind": "unknown",
        "tool_name": tool_name,
        "tool_args": tool_args,
    }


def build_approval_prompt(tool_name: str, preview: dict[str, Any]) -> str:
    kind = preview.get("kind")
    if kind == "set_goal":
        previous = preview.get("previous_daily_calorie_goal")
        goal = int(preview.get("daily_calorie_goal") or 0)
        if previous is not None and int(previous) == goal:
            return f"您的每日热量目标已是 **{goal} kcal**，无需重复设置。"
        if previous is not None:
            return (
                f"请确认是否将每日热量目标从 **{int(previous)} kcal** "
                f"更新为 **{goal} kcal**？"
            )
        return f"请确认是否将每日热量目标设为 **{goal} kcal**？"

    if kind == "log_meal":
        meal_label = MEAL_TYPE_LABELS.get(str(preview.get("meal_type")), "餐食")
        total = preview.get("total_kcal") or 0
        lines = [f"请确认是否将以下 **{meal_label}** 记入今日日记（合计约 **{int(total)} kcal**）："]
        for item in preview.get("items") or []:
            name = item.get("name") or "食物"
            kcal = int(float(item.get("kcal") or 0))
            qty = item.get("qty")
            unit = item.get("unit") or ""
            portion = f" {qty}{unit}" if qty else ""
            lines.append(f"- {name}{portion}（约 {kcal} kcal）")
        return "\n".join(lines)

    if kind == "delete_entry":
        entry_id = preview.get("entry_id") or ""
        return f"请确认是否删除日记记录 **{entry_id}**？此操作不可撤销。"

    return "请确认是否执行该操作。"


def build_approval_success_message(tool_name: str, result: dict[str, Any] | None) -> str:
    if tool_name == "set_daily_calorie_goal" and result:
        goal = int(result.get("daily_calorie_goal") or 0)
        return f"已确认：每日热量目标已更新为 **{goal} kcal**。"

    if tool_name == "log_meal" and result:
        total = int(float(result.get("total_kcal") or 0))
        meal_label = MEAL_TYPE_LABELS.get(str(result.get("meal_type")), "餐食")
        return f"已确认：**{meal_label}** 已记入今日日记（约 **{total} kcal**）。"

    if tool_name == "delete_diary_entry":
        if result and result.get("ok"):
            return "已确认：日记记录已删除。"
        return "删除失败：未找到对应记录。"

    return "操作已确认完成。"


async def execute_write_tool(
    *,
    tool_name: str,
    tool_args: dict[str, Any],
    fitness_service: FitnessService,
    user_id: Any,
    user_timezone: str | None,
) -> dict[str, Any]:
    if tool_name == "set_daily_calorie_goal":
        goal = tool_args.get("daily_calorie_goal")
        if goal is None:
            parsed = FitnessGoalUpdate.model_validate(tool_args)
            goal = parsed.daily_calorie_goal
        updated = await fitness_service.set_goal(
            user_id=user_id,
            daily_calorie_goal=int(goal),
        )
        return updated.model_dump(mode="json")

    if tool_name == "log_meal":
        entry = await fitness_service.log_meal(
            user_id=user_id,
            meal_type=str(tool_args.get("meal_type") or "lunch"),
            items=list(tool_args.get("items") or []),
            note=tool_args.get("note"),
            timezone_name=user_timezone,
        )
        return entry.model_dump(mode="json")

    if tool_name == "delete_diary_entry":
        ok = await fitness_service.delete_entry(
            user_id=user_id,
            entry_id=str(tool_args.get("entry_id") or ""),
        )
        return {"ok": ok}

    raise ValueError(f"Unsupported write tool: {tool_name}")
