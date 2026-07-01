"""Normalize chat messages before sending to OpenAI-compatible APIs."""

from __future__ import annotations

from typing import Any

from .types import ChatMessage


def sanitize_messages_for_api(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """Ensure no null string fields (DeepSeek rejects null content / tool_call ids)."""
    converted: list[dict[str, Any]] = []

    for msg in messages:
        item = dict(msg)
        role = item.get("role")

        if role in ("system", "user", "assistant", "tool") and item.get("content") is None:
            item["content"] = ""

        if role == "assistant" and item.get("tool_calls"):
            item["content"] = item.get("content") or ""
            item["tool_calls"] = _sanitize_tool_calls(item["tool_calls"])

        if role == "tool":
            item["content"] = item.get("content") or ""
            item["tool_call_id"] = item.get("tool_call_id") or "call_unknown"
            item.pop("tool_calls", None)

        # Drop top-level nulls (keep empty strings)
        cleaned = {k: v for k, v in item.items() if v is not None}
        if role == "assistant" and cleaned.get("tool_calls") and "content" not in cleaned:
            cleaned["content"] = ""
        converted.append(cleaned)

    return converted


def _sanitize_tool_calls(tool_calls: list[dict]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for i, tc in enumerate(tool_calls or []):
        if not tc:
            continue
        tc = dict(tc)
        func = dict(tc.get("function") or {})
        name = (func.get("name") or "").strip()
        if not name:
            continue
        sanitized.append(
            {
                "id": tc.get("id") or f"call_{i}_{name}",
                "type": tc.get("type") or "function",
                "function": {
                    "name": name,
                    "arguments": func.get("arguments") if func.get("arguments") is not None else "{}",
                },
            }
        )
    return sanitized
