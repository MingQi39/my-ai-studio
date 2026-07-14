"""Helpers for DeepAgent write_todos → SSE todos_updated."""

from __future__ import annotations

from typing import Any

_ALLOWED_STATUS = frozenset({"pending", "in_progress", "completed"})


def normalize_todos(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    result: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        status = item.get("status")
        if not isinstance(content, str) or not content.strip():
            continue
        if status not in _ALLOWED_STATUS:
            continue
        result.append({"content": content.strip(), "status": str(status)})
    return result


def build_todos_updated_event(raw_todos: Any) -> dict[str, Any] | None:
    todos = normalize_todos(raw_todos)
    if not todos:
        return None
    return {"type": "todos_updated", "source": "agent", "todos": todos}
