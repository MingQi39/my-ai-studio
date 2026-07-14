"""In-memory checkpoint state for spider SSE persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.spider.services.todo_events import normalize_todos

PersistAction = Literal["immediate", "debounced", "none"]


@dataclass
class SpiderCheckpointState:
    content_buffer: str = ""
    pending: dict[str, dict[str, Any]] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    has_error: bool = False
    failure: dict[str, Any] | None = None
    latest_todos: list[dict[str, str]] | None = None


def ordered_tool_trace(state: SpiderCheckpointState) -> list[dict[str, Any]]:
    return [state.pending[call_id] for call_id in state.order if call_id in state.pending]


def has_persistable_snapshot(state: SpiderCheckpointState) -> bool:
    return bool(
        state.content_buffer
        or state.order
        or state.failure
        or state.latest_todos
    )


def resolve_persist_content(state: SpiderCheckpointState, *, complete: bool) -> str:
    if state.content_buffer:
        return state.content_buffer
    if not complete:
        return ""
    if state.has_error:
        return "任务执行失败"
    return "（无回复内容）"


def apply_persist_event(state: SpiderCheckpointState, event: dict[str, Any]) -> PersistAction:
    etype = event.get("type")

    if etype == "chunk" and event.get("content"):
        state.content_buffer += str(event["content"])
        return "debounced"

    if etype == "final_response" and event.get("content"):
        state.content_buffer = str(event["content"])
        return "debounced"

    if etype == "tool_call_start":
        call_id = str(event.get("call_id") or "")
        if not call_id:
            return "none"
        entry: dict[str, Any] = {
            "id": call_id,
            "tool_name": event.get("tool_name") or event.get("raw_tool_name") or "unknown",
            "tool_args": event.get("tool_args") or {},
            "status": "pending",
        }
        if event.get("raw_tool_name"):
            entry["raw_tool_name"] = event.get("raw_tool_name")
        if call_id not in state.pending:
            state.order.append(call_id)
        state.pending[call_id] = entry
        return "immediate"

    if etype == "tool_call_result":
        call_id = str(event.get("call_id") or "")
        if not call_id or call_id not in state.pending:
            return "none"
        entry = state.pending[call_id]
        entry["result"] = event.get("result")
        entry["status"] = event.get("status") or ("error" if event.get("error") else "success")
        if event.get("error") is not None:
            entry["error"] = event.get("error")
        return "immediate"

    if etype == "todos_updated":
        normalized = normalize_todos(event.get("todos"))
        if not normalized:
            return "none"
        state.latest_todos = normalized
        return "immediate"

    if etype == "error":
        state.has_error = True
        if event.get("message"):
            state.content_buffer = str(event["message"])
        state.failure = {
            "code": event.get("code"),
            "title": event.get("title") or "任务执行失败",
            "detail": event.get("detail") or event.get("message") or "",
            "hints": event.get("hints") or [],
            "stage": event.get("stage"),
            "recoverable": bool(event.get("recoverable")),
        }
        return "immediate"

    return "none"
