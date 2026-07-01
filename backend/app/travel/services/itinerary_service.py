"""Generate structured travel plans from chat context."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.models.database import MessageRole, SessionType
from app.services.session_service import SessionService
from app.travel.itinerary_models import (
    PlanActivity,
    PlanBudgetItem,
    PlanDay,
    PlanLocation,
    StructuredTravelPlan,
    ToolEvidenceItem,
    TravelPlanGenerateResponse,
)
from app.travel.services.chat_persistence import parse_travel_meta
from app.travel.services.openai_client import complete_chat
from app.travel.services.plan_links import build_amap_search_url, collect_plan_locations

ITINERARY_SYSTEM_PROMPT = """你是旅行规划文档编辑。根据用户的出行需求和助手已给出的规划文本，整理成结构化 JSON。

要求：
1. 只输出合法 JSON，不要 Markdown 代码块或额外说明
2. 保留原规划中的关键信息，合理拆分到每日行程
3. 若信息不足，可合理推断并标注在 tips 中提醒用户核实
4. 有工具验证数据时优先采用工具结果；否则以助手文本为准
5. daily_itinerary 至少 1 天；activities 按时间顺序排列
6. budget_total 与 budget_breakdown 尽量一致；无法估算则留 null
7. data_verified 由输入中的 data_verified 字段决定，不要自行修改
8. daily_itinerary 的 activities 应包含用餐安排（午餐、晚餐或特色小吃）；有 search_food_recommendations 工具数据时优先引用

JSON 结构：
{
  "title": "行程标题",
  "destination": "目的地",
  "duration_days": 3,
  "travel_dates": "2026-05-01 至 2026-05-03 或 null",
  "budget_total": 5000,
  "budget_currency": "CNY",
  "summary": "2-3 句概览",
  "weather_summary": "天气摘要或 null",
  "daily_itinerary": [
    {
      "day": 1,
      "title": "Day 1 主题或 null",
      "activities": [
        {
          "time": "09:00 或 上午",
          "title": "活动名称",
          "description": "说明或 null",
          "location": {"name": "地点", "address": "地址或 null", "note": "备注或 null"}
        }
      ]
    }
  ],
  "accommodations": [{"name": "酒店", "address": "地址或 null", "note": "备注或 null"}],
  "transport": ["交通方式说明"],
  "budget_breakdown": [{"category": "类别", "amount": 1000, "currency": "CNY", "note": "备注或 null"}],
  "tips": ["注意事项"],
  "data_verified": false
}"""


def _parse_json_content(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        text = fence_match.group(1).strip()
    return json.loads(text)


def structured_plan_to_markdown(plan: StructuredTravelPlan) -> str:
    exported_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    lines: list[str] = [
        f"# {plan.title}",
        "",
        f"> 导出时间：{exported_at}",
        "",
        "## 行程概览",
        "",
        f"- **目的地**：{plan.destination}",
    ]

    if plan.duration_days:
        lines.append(f"- **天数**：{plan.duration_days} 天")
    if plan.travel_dates:
        lines.append(f"- **日期**：{plan.travel_dates}")
    if plan.budget_total is not None:
        lines.append(f"- **预算**：{plan.budget_total:g} {plan.budget_currency}")
    if plan.data_verified:
        lines.append("- **数据来源**：Agent 工具验证")
    else:
        lines.append("- **数据来源**：AI 整理，出行前请核实")

    lines.extend(["", plan.summary, ""])

    if plan.weather_summary:
        lines.extend(["## 天气参考", "", plan.weather_summary, ""])

    if plan.daily_itinerary:
        lines.append("## 每日行程")
        lines.append("")
        for day in plan.daily_itinerary:
            day_title = day.title or f"第 {day.day} 天"
            lines.append(f"### Day {day.day} · {day_title}")
            lines.append("")
            for activity in day.activities:
                time_prefix = f"**{activity.time}** " if activity.time else ""
                lines.append(f"- {time_prefix}{activity.title}")
                if activity.description:
                    lines.append(f"  - {activity.description}")
                if activity.location:
                    loc = activity.location
                    loc_line = loc.name
                    if loc.address:
                        loc_line += f"（{loc.address}）"
                    lines.append(f"  - 📍 {loc_line}")
                    lines.append(
                        f"  - [高德导航]({build_amap_search_url(loc.name, address=loc.address, city=plan.destination)})"
                    )
                    if loc.note:
                        lines.append(f"  - {loc.note}")
            lines.append("")

    if plan.accommodations:
        lines.extend(["## 住宿推荐", ""])
        for item in plan.accommodations:
            line = f"- **{item.name}**"
            if item.address:
                line += f" — {item.address}"
            lines.append(line)
            lines.append(
                f"  - [高德导航]({build_amap_search_url(item.name, address=item.address, city=plan.destination)})"
            )
            if item.note:
                lines.append(f"  - {item.note}")
        lines.append("")

    nav_locations = collect_plan_locations(plan)
    if nav_locations:
        lines.extend(["## 导航链接", ""])
        for item in nav_locations:
            label = item["name"]
            if item["address"]:
                label += f"（{item['address']}）"
            lines.append(f"- [{label}]({item['url']})")
        lines.append("")

    if plan.transport:
        lines.extend(["## 交通安排", ""])
        for item in plan.transport:
            lines.append(f"- {item}")
        lines.append("")

    if plan.budget_breakdown:
        lines.extend(["## 预算明细", ""])
        lines.append("| 类别 | 金额 | 说明 |")
        lines.append("| --- | ---: | --- |")
        for item in plan.budget_breakdown:
            amount = f"{item.amount:g} {item.currency}" if item.amount is not None else "—"
            note = item.note or "—"
            lines.append(f"| {item.category} | {amount} | {note} |")
        lines.append("")

    if plan.tips:
        lines.extend(["## 注意事项", ""])
        for tip in plan.tips:
            lines.append(f"- {tip}")
        lines.append("")

    lines.extend(["---", "", "*由 AI 生成，出行前请核实交通、票价与开放时间。*"])
    return "\n".join(lines)


def _format_tool_evidence(items: list[ToolEvidenceItem]) -> str:
    if not items:
        return "（无工具验证数据）"

    chunks: list[str] = []
    for item in items[:12]:
        chunks.append(f"### {item.tool_name}\n{item.result[:2000]}")
    return "\n\n".join(chunks)


def _is_verified_mode(mode: str | None) -> bool:
    return mode in ("agent", "compare_agent")


_LOADING_CONTENT_PREFIXES = ("🔄", "💭", "🔍", "✍️", "❌", "正在", "等待")


def _is_valid_assistant_plan_content(content: str) -> bool:
    text = content.strip()
    if not text or text.startswith("❌"):
        return False
    if any(text.startswith(prefix) for prefix in _LOADING_CONTENT_PREFIXES):
        return False
    return len(text) >= 30


def extract_latest_plan_from_messages(
    messages: list[Any],
) -> tuple[str, str, bool] | None:
    sorted_messages = sorted(messages, key=lambda msg: msg.created_at)
    assistant_msg = None
    for msg in reversed(sorted_messages):
        role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
        if role == MessageRole.assistant.value and _is_valid_assistant_plan_content(msg.content):
            assistant_msg = msg
            break

    if assistant_msg is None:
        return None

    user_msg = None
    assistant_index = sorted_messages.index(assistant_msg)
    for msg in reversed(sorted_messages[:assistant_index]):
        role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
        if role == MessageRole.user.value:
            user_msg = msg
            break

    if user_msg is None:
        return None

    meta = parse_travel_meta(assistant_msg.tool_calls)
    mode = meta.get("mode") if meta else None
    return user_msg.content.strip(), assistant_msg.content.strip(), _is_verified_mode(mode)


async def resolve_plan_inputs(
    session_service: SessionService,
    user_id: UUID,
    *,
    session_id: UUID | None,
    user_request: str | None,
    assistant_plan: str | None,
    data_verified: bool,
) -> tuple[str, str, bool]:
    if user_request and assistant_plan:
        return user_request.strip(), assistant_plan.strip(), data_verified

    if not session_id:
        raise ValueError("请提供 session_id 或 user_request + assistant_plan")

    session = await session_service.get_session(session_id, user_id)
    if not session:
        raise ValueError("Session not found")
    if session.session_type != SessionType.travel:
        raise ValueError("Not a travel session")

    messages = await session_service.get_messages(session_id)
    extracted = extract_latest_plan_from_messages(messages)
    if not extracted:
        raise ValueError("当前会话没有可整理的规划内容")

    req, plan, verified = extracted
    return req, plan, verified or data_verified


async def generate_structured_plan(
    openai_client: Any,
    model_name: str,
    *,
    user_request: str,
    assistant_plan: str,
    tool_evidence: list[ToolEvidenceItem],
    data_verified: bool,
) -> TravelPlanGenerateResponse:
    user_payload = {
        "user_request": user_request,
        "assistant_plan": assistant_plan,
        "data_verified": data_verified,
        "tool_evidence": _format_tool_evidence(tool_evidence),
    }

    raw = await complete_chat(
        openai_client,
        [
            {"role": "system", "content": ITINERARY_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False),
            },
        ],
        model_name,
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    try:
        payload = _parse_json_content(raw)
        payload["data_verified"] = data_verified
        plan = StructuredTravelPlan.model_validate(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"无法解析结构化行程: {exc}") from exc

    markdown = structured_plan_to_markdown(plan)
    return TravelPlanGenerateResponse(plan=plan, markdown=markdown)
