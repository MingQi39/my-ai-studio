"""Tests for API message sanitization."""

from app.core.adapters.message_utils import sanitize_messages_for_api
from app.core.streaming import StreamBuffer
from app.services.chat_tools.registry import ToolsRegistry
from app.services.chat_tools.resolve import resolve_tool_calls


def test_sanitize_assistant_tool_calls_null_id():
    result = sanitize_messages_for_api(
        [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "index": 0,
                        "id": None,
                        "type": "function",
                        "function": {"name": "web_search", "arguments": '{"query":"test"}'},
                    }
                ],
            }
        ]
    )
    msg = result[0]
    assert msg["content"] == ""
    assert msg["tool_calls"][0]["id"] == "call_0_web_search"
    assert msg["tool_calls"][0]["function"]["arguments"] == '{"query":"test"}'


def test_sanitize_tool_message_null_content():
    result = sanitize_messages_for_api(
        [{"role": "tool", "tool_call_id": None, "content": None}]
    )
    msg = result[0]
    assert msg["content"] == ""
    assert msg["tool_call_id"] == "call_unknown"


def test_resolve_missing_tool_name_single_tool():
    registry = ToolsRegistry()
    registry.register(
        name="web_search",
        description="search",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=lambda **_: "ok",
    )
    resolved = resolve_tool_calls(
        [{"index": 0, "function": {"name": "", "arguments": "{}"}}],
        registry,
    )
    assert resolved[0]["function"]["name"] == "web_search"


def test_stream_buffer_merge_by_index():
    buf = StreamBuffer()
    buf.append({"type": "tool_call", "tool_call": {"index": 0, "function": {"arguments": '{"query"'}}})
    buf.append({"type": "tool_call", "tool_call": {"index": 0, "function": {"arguments": ':"x"}', "name": "web_search"}}})
    buf.append({"type": "tool_call", "tool_call": {"index": 0, "id": "call_abc"}})
    calls = buf.get_tool_calls()
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "web_search"
    assert calls[0]["function"]["arguments"] == '{"query":"x"}'
    assert calls[0]["id"] == "call_abc"
