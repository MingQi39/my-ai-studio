"""Helpers for todos_updated (DeepAgent write_todos + Pipeline template)."""

from __future__ import annotations

from typing import Any

_ALLOWED_STATUS = frozenset({"pending", "in_progress", "completed", "failed"})

PIPELINE_TODO_CONTENTS: tuple[str, ...] = (
    "分析目标网站结构",
    "生成爬虫代码",
    "在沙箱执行并调试",
    "清洗并校验数据",
)


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


def pipeline_todo_snapshot(
    *,
    completed_through: int = -1,
    active_index: int | None = None,
    failed_index: int | None = None,
) -> list[dict[str, str]]:
    """Build the fixed 4-step pipeline todo snapshot.

    - Indices ``0..completed_through`` (inclusive) → completed
    - ``failed_index`` (if set) → failed
    - ``active_index`` (if set and not failed) → in_progress
    - remaining → pending
    """
    todos: list[dict[str, str]] = []
    for i, content in enumerate(PIPELINE_TODO_CONTENTS):
        if failed_index is not None and i == failed_index:
            status = "failed"
        elif i <= completed_through:
            status = "completed"
        elif active_index is not None and i == active_index:
            status = "in_progress"
        else:
            status = "pending"
        todos.append({"content": content, "status": status})
    return todos
