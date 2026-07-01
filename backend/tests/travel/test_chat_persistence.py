"""Tests for travel chat persistence helpers."""

from app.travel.services.chat_persistence import (
    build_travel_tool_calls,
    collect_agent_thinking_event,
    messages_to_history,
    parse_travel_meta,
)


def test_build_and_parse_travel_meta():
    tool_calls = build_travel_tool_calls(
        mode="agent",
        thinking_steps=[{"type": "Think", "content": "分析中", "round": 1, "sequence": 1}],
    )
    meta = parse_travel_meta(tool_calls)
    assert meta is not None
    assert meta["mode"] == "agent"
    assert meta["thinking_steps"][0]["content"] == "分析中"


def test_messages_to_history():
    from datetime import datetime, timezone

    class _FakeMessage:
        def __init__(self, role: str, content: str, created_at: datetime):
            self.role = type("Role", (), {"value": role})()
            self.content = content
            self.created_at = created_at

    t1 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 1, 10, 1, tzinfo=timezone.utc)

    history = messages_to_history(
        [
            _FakeMessage("assistant", "你好，需要规划什么旅行？", t2),
            _FakeMessage("user", "你好", t1),
        ]
    )
    assert history == [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好，需要规划什么旅行？"},
    ]


def test_collect_agent_thinking_event_with_tool_calls():
    thinking_steps: list = []
    pending: dict = {}

    collect_agent_thinking_event(
        {
            "type": "tool_call_start",
            "call_id": "call-1",
            "tool_name": "get_weather",
            "tool_args": {"city": "杭州"},
        },
        thinking_steps,
        pending,
    )
    collect_agent_thinking_event(
        {
            "type": "tool_call_result",
            "call_id": "call-1",
            "result": '{"city":"杭州"}',
            "status": "success",
            "duration_ms": 120,
        },
        thinking_steps,
        pending,
    )
    collect_agent_thinking_event(
        {
            "type": "step",
            "step_type": "Act",
            "content": "执行工具",
            "round": 1,
            "sequence": 3,
        },
        thinking_steps,
        pending,
    )

    assert len(thinking_steps) == 1
    assert thinking_steps[0]["type"] == "Act"
    assert thinking_steps[0]["toolCalls"][0]["tool_name"] == "get_weather"
    assert thinking_steps[0]["toolCalls"][0]["result"] == '{"city":"杭州"}'


def test_collect_agent_thinking_event_attaches_observe_tool_calls():
    thinking_steps: list = []
    pending: dict = {}

    collect_agent_thinking_event(
        {
            "type": "tool_call_start",
            "call_id": "observe-food-1",
            "tool_name": "search_food_recommendations",
            "tool_args": {"city": "成都"},
        },
        thinking_steps,
        pending,
    )
    collect_agent_thinking_event(
        {
            "type": "tool_call_result",
            "call_id": "observe-food-1",
            "result": '{"city":"成都","count":2}',
            "status": "success",
            "duration_ms": 80,
        },
        thinking_steps,
        pending,
    )
    collect_agent_thinking_event(
        {
            "type": "step",
            "step_type": "Observe",
            "content": "[环境观察] 美食",
            "round": 1,
            "sequence": 2,
        },
        thinking_steps,
        pending,
    )

    assert len(thinking_steps) == 1
    assert thinking_steps[0]["type"] == "Observe"
    assert thinking_steps[0]["toolCalls"][0]["tool_name"] == "search_food_recommendations"
