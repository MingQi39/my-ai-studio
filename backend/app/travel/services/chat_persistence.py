"""Travel chat session persistence helpers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.models.database import MessageRole, SessionType
from app.models.schemas import MessageCreate, SessionCreate
from app.services.session_service import SessionService

TRAVEL_META_KEY = "travel_meta"


def build_travel_tool_calls(
    *,
    mode: str,
    thinking_steps: list[dict[str, Any]] | None = None,
    compare_group: str | None = None,
) -> list[dict[str, Any]]:
    meta: dict[str, Any] = {"type": TRAVEL_META_KEY, "mode": mode}
    if thinking_steps:
        meta["thinking_steps"] = thinking_steps
    if compare_group:
        meta["compare_group"] = compare_group
    return [meta]


def parse_travel_meta(tool_calls: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    if not tool_calls:
        return None
    for item in tool_calls:
        if isinstance(item, dict) and item.get("type") == TRAVEL_META_KEY:
            return item
    return None


def messages_to_history(messages: list[Any]) -> list[dict[str, str]]:
    """Convert stored messages to simple role/content history (chronological order)."""
    sorted_messages = sorted(messages, key=lambda m: m.created_at)
    history: list[dict[str, str]] = []
    for msg in sorted_messages:
        role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
        if role in ("user", "assistant"):
            history.append({"role": role, "content": msg.content})
    return history


def collect_agent_thinking_event(
    event: dict[str, Any],
    thinking_steps: list[dict[str, Any]],
    pending_tool_calls: dict[str, dict[str, Any]],
) -> None:
    """Accumulate ReAct steps and tool call details for session persistence."""
    event_type = event.get("type")

    if event_type == "tool_call_start":
        call_id = event.get("call_id")
        if not call_id:
            return
        pending_tool_calls[str(call_id)] = {
            "id": str(call_id),
            "tool_name": event.get("tool_name") or event.get("tool") or "unknown",
            "tool_args": event.get("tool_args") or event.get("args") or {},
            "status": "pending",
        }
        return

    if event_type == "tool_call_result":
        call_id = event.get("call_id")
        if not call_id:
            return
        entry = pending_tool_calls.get(str(call_id))
        if not entry:
            return
        entry["result"] = event.get("result")
        entry["status"] = event.get("status") or ("error" if event.get("error") else "success")
        entry["duration_ms"] = event.get("duration_ms")
        if event.get("error"):
            entry["error"] = event.get("error")
        return

    if event_type == "step" and event.get("content"):
        step: dict[str, Any] = {
            "type": event.get("step_type"),
            "content": event.get("content"),
            "round": event.get("round", 0),
            "sequence": event.get("sequence", 0),
        }
        if event.get("step_type") in ("Act", "Observe"):
            completed = [
                tool_call
                for tool_call in pending_tool_calls.values()
                if tool_call.get("status") != "pending"
            ]
            if completed:
                step["toolCalls"] = completed
            pending_tool_calls.clear()
        thinking_steps.append(step)


async def resolve_travel_session(
    session_service: SessionService,
    user_id: UUID,
    session_id: UUID | None,
    first_message: str,
) -> tuple[UUID, bool]:
    """Get or create a travel session. Returns (session_id, created)."""
    if session_id:
        session = await session_service.get_session(session_id, user_id)
        if not session:
            raise ValueError("Session not found")
        if session.session_type != SessionType.travel:
            raise ValueError("Not a travel session")
        return session_id, False

    title = first_message.strip()[:20] + ("..." if len(first_message.strip()) > 20 else "")
    if not title:
        title = "旅行规划"
    session = await session_service.create_session(
        user_id,
        SessionCreate(title=title, session_type=SessionType.travel),
    )
    return UUID(str(session.id)), True


async def save_travel_user_message(
    session_service: SessionService,
    session_id: UUID,
    content: str,
    *,
    user_id: UUID | None = None,
) -> None:
    await session_service.add_message(
        session_id,
        MessageCreate(role=MessageRole.user, content=content),
    )
    if user_id is not None:
        from app.travel.services.formal_plan_storage import clear_formal_plan

        await clear_formal_plan(session_service, session_id, user_id)


async def save_travel_assistant_message(
    session_service: SessionService,
    session_id: UUID,
    content: str,
    *,
    mode: str,
    thinking_steps: list[dict[str, Any]] | None = None,
    compare_group: str | None = None,
) -> None:
    await session_service.add_message(
        session_id,
        MessageCreate(
            role=MessageRole.assistant,
            content=content,
            tool_calls=build_travel_tool_calls(
                mode=mode,
                thinking_steps=thinking_steps,
                compare_group=compare_group,
            ),
        ),
    )
