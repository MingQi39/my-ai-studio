"""Tests for structured travel plan generation helpers."""

from datetime import datetime, timezone

from app.travel.itinerary_models import (
    PlanActivity,
    PlanBudgetItem,
    PlanDay,
    PlanLocation,
    StructuredTravelPlan,
)
from app.travel.services.chat_persistence import build_travel_tool_calls
from app.travel.services.itinerary_service import (
    extract_latest_plan_from_messages,
    structured_plan_to_markdown,
)


def test_structured_plan_to_markdown_contains_sections():
    plan = StructuredTravelPlan(
        title="杭州三日游",
        destination="杭州",
        duration_days=3,
        travel_dates="2026-05-01 至 2026-05-03",
        budget_total=5000,
        summary="西湖、灵隐寺与龙井村轻松游。",
        weather_summary="晴间多云，适合出行",
        daily_itinerary=[
            PlanDay(
                day=1,
                title="西湖环线",
                activities=[
                    PlanActivity(
                        time="09:00",
                        title="断桥残雪",
                        description="沿北山街步行",
                        location=PlanLocation(name="断桥", address="杭州市西湖区"),
                    )
                ],
            )
        ],
        accommodations=[PlanLocation(name="西湖边酒店", address="北山街")],
        transport=["高铁 G1234"],
        budget_breakdown=[PlanBudgetItem(category="住宿", amount=1800, note="两晚")],
        tips=["提前预约灵隐寺门票"],
        data_verified=True,
    )

    markdown = structured_plan_to_markdown(plan)

    assert "# 杭州三日游" in markdown
    assert "## 每日行程" in markdown
    assert "Day 1" in markdown
    assert "## 预算明细" in markdown
    assert "Agent 工具验证" in markdown


def test_extract_latest_plan_from_messages():
    class _FakeMessage:
        def __init__(self, role: str, content: str, created_at: datetime, tool_calls=None):
            self.role = type("Role", (), {"value": role})()
            self.content = content
            self.created_at = created_at
            self.tool_calls = tool_calls

    t1 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 1, 10, 1, tzinfo=timezone.utc)

    extracted = extract_latest_plan_from_messages(
        [
            _FakeMessage("user", "规划杭州3日游", t1),
            _FakeMessage(
                "assistant",
                "Day1 西湖断桥残雪，Day2 灵隐寺飞来峰，Day3 龙井村品茶。",
                t2,
                tool_calls=build_travel_tool_calls(mode="agent"),
            ),
        ]
    )

    assert extracted == ("规划杭州3日游", "Day1 西湖断桥残雪，Day2 灵隐寺飞来峰，Day3 龙井村品茶。", True)
