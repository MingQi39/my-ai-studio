import pytest
from types import SimpleNamespace

from app.travel.services.react_agent import ReActAgent, needs_departure_clarification


class _NoToolRegistry:
    async def execute(self, name, args):
        raise AssertionError(f"缺少出发地时不应调用工具: {name}({args})")

    def to_openai_tools(self):
        return []


class _NoLLMClient:
    @property
    def chat(self):
        raise AssertionError("缺少出发地时不应调用模型")


class _RecordingToolRegistry:
    def __init__(self):
        self.calls = []

    async def execute(self, name, args):
        self.calls.append((name, args))
        return "{}"

    def to_openai_tools(self):
        return []


class _CompletingLLMClient:
    def __init__(self):
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create),
        )

    async def _create(self, **_kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="已获取足够信息", tool_calls=None),
                ),
            ],
        )


@pytest.mark.asyncio
async def test_trip_plan_without_departure_city_asks_before_planning():
    agent = ReActAgent(
        tools_registry=_NoToolRegistry(),
        openai_client=_NoLLMClient(),
    )

    events = [
        event
        async for event in agent.run(
            "请帮我规划一个去川西拍婚纱照加游玩的8天7夜行程，计划是十月一左右出发",
        )
    ]

    final_responses = [
        event["content"] for event in events if event["type"] == "final_response"
    ]
    assert len(final_responses) == 1
    assert "从哪里出发" in final_responses[0]
    assert "杭州" not in final_responses[0]
    assert [event["type"] for event in events] == ["start", "final_response", "done"]


@pytest.mark.asyncio
async def test_departure_answer_continues_original_trip_without_treating_it_as_destination():
    registry = _RecordingToolRegistry()
    agent = ReActAgent(
        tools_registry=registry,
        openai_client=_CompletingLLMClient(),
    )
    original_request = (
        "请帮我规划一个去川西拍婚纱照加游玩的8天7夜行程，计划是十月一左右出发"
    )
    history = [
        {"role": "user", "content": original_request},
        {
            "role": "assistant",
            "content": "你准备从哪里出发（告诉我城市即可）？",
        },
    ]

    events = [
        event
        async for event in agent.run(
            "杭州",
            max_rounds=1,
            conversation_history=history,
        )
    ]

    assert any(event["type"] == "round_start" for event in events)
    assert registry.calls == [
        ("get_weather", {"city": "川西"}),
        ("search_food_recommendations", {"city": "川西"}),
    ]


def test_explicit_departure_does_not_trigger_clarification():
    assert not needs_departure_clarification(
        "请从杭州出发，规划一个去川西拍婚纱照加游玩的8天7夜行程"
    )
