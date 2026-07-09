"""Fitness chat session persistence helpers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.models.database import MessageRole, SessionType
from app.models.schemas import MessageCreate, SessionCreate
from app.services.session_service import SessionService

FITNESS_META_KEY = "fitness_meta"


def build_fitness_tool_calls(
    *,
    tool_trace: list[dict[str, Any]] | None = None,
    meal_logged: dict[str, Any] | None = None,
    recommendations: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    meta: dict[str, Any] = {"type": FITNESS_META_KEY}
    if tool_trace:
        meta["tool_trace"] = tool_trace
    if meal_logged:
        meta["meal_logged"] = meal_logged
    if recommendations:
        meta["recommendations"] = recommendations
    return [meta]


def parse_fitness_meta(tool_calls: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    if not tool_calls:
        return None
    for item in tool_calls:
        if isinstance(item, dict) and item.get("type") == FITNESS_META_KEY:
            return item
    return None


def messages_to_history(messages: list[Any]) -> list[dict[str, str]]:
    sorted_messages = sorted(messages, key=lambda m: m.created_at)
    history: list[dict[str, str]] = []
    for msg in sorted_messages:
        role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
        if role in ("user", "assistant"):
            history.append({"role": role, "content": msg.content})
    return history


async def resolve_fitness_session(
    session_service: SessionService,
    user_id: UUID,
    session_id: UUID | None,
    first_message: str,
) -> tuple[UUID, bool]:
    if session_id:
        session = await session_service.get_session(session_id, user_id)
        if not session:
            raise ValueError("Session not found")
        if session.session_type != SessionType.fitness:
            raise ValueError("Not a fitness session")
        return session_id, False

    title = first_message.strip()[:20] + ("..." if len(first_message.strip()) > 20 else "")
    if not title:
        title = "Fitness"
    session = await session_service.create_session(
        user_id,
        SessionCreate(title=title, session_type=SessionType.fitness),
    )
    return UUID(str(session.id)), True


async def save_fitness_user_message(
    session_service: SessionService,
    session_id: UUID,
    content: str,
) -> None:
    await session_service.add_message(
        session_id,
        MessageCreate(role=MessageRole.user, content=content),
    )


async def save_fitness_assistant_message(
    session_service: SessionService,
    session_id: UUID,
    content: str,
    *,
    tool_trace: list[dict[str, Any]] | None = None,
    meal_logged: dict[str, Any] | None = None,
    recommendations: list[dict[str, Any]] | None = None,
) -> None:
    await session_service.add_message(
        session_id,
        MessageCreate(
            role=MessageRole.assistant,
            content=content,
            tool_calls=build_fitness_tool_calls(
                tool_trace=tool_trace,
                meal_logged=meal_logged,
                recommendations=recommendations,
            ),
        ),
    )
