"""Spider chat session persistence helpers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.models.database import MessageRole, SessionType
from app.models.schemas import MessageCreate, SessionCreate
from app.services.session_service import SessionService

SPIDER_META_KEY = "spider_meta"


def build_spider_tool_calls(
    *,
    tool_trace: list[dict[str, Any]] | None = None,
    target_url: str | None = None,
    failure: dict[str, Any] | None = None,
    todos: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    meta: dict[str, Any] = {"type": SPIDER_META_KEY}
    if tool_trace:
        meta["tool_trace"] = tool_trace
    if target_url:
        meta["target_url"] = target_url
    if failure:
        meta["failure"] = failure
    if todos:
        meta["todos"] = todos
    return [meta]


def parse_spider_meta(tool_calls: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    if not tool_calls:
        return None
    for item in tool_calls:
        if isinstance(item, dict) and item.get("type") == SPIDER_META_KEY:
            return item
    return None


def messages_to_history(messages: list[Any]) -> list[dict[str, str]]:
    sorted_messages = sorted(messages, key=lambda message: message.created_at)
    history: list[dict[str, str]] = []
    for message in sorted_messages:
        role = message.role.value if hasattr(message.role, "value") else str(message.role)
        if role in ("user", "assistant"):
            history.append({"role": role, "content": message.content})
    return history


async def resolve_spider_session(
    session_service: SessionService,
    user_id: UUID,
    session_id: UUID | None,
    first_message: str,
) -> tuple[UUID, bool]:
    if session_id:
        session = await session_service.get_session(session_id, user_id)
        if not session:
            raise ValueError("Session not found")
        if session.session_type != SessionType.spider:
            raise ValueError("Not a spider session")
        return session_id, False

    title = first_message.strip()[:20] + ("..." if len(first_message.strip()) > 20 else "")
    if not title:
        title = "Spider"
    session = await session_service.create_session(
        user_id,
        SessionCreate(title=title, session_type=SessionType.spider),
    )
    return UUID(str(session.id)), True


async def save_spider_user_message(
    session_service: SessionService,
    session_id: UUID,
    content: str,
    *,
    target_url: str | None = None,
) -> None:
    tool_calls = build_spider_tool_calls(target_url=target_url) if target_url else None
    await session_service.add_message(
        session_id,
        MessageCreate(role=MessageRole.user, content=content, tool_calls=tool_calls),
    )


async def save_spider_assistant_message(
    session_service: SessionService,
    session_id: UUID,
    content: str,
    *,
    tool_trace: list[dict[str, Any]] | None = None,
    failure: dict[str, Any] | None = None,
    todos: list[dict[str, Any]] | None = None,
) -> None:
    await upsert_spider_assistant_message(
        session_service=session_service,
        session_id=session_id,
        message_id=None,
        content=content,
        tool_trace=tool_trace,
        failure=failure,
        todos=todos,
        is_complete=True,
    )


async def upsert_spider_assistant_message(
    session_service: SessionService,
    session_id: UUID,
    content: str,
    *,
    message_id: UUID | None = None,
    tool_trace: list[dict[str, Any]] | None = None,
    failure: dict[str, Any] | None = None,
    todos: list[dict[str, Any]] | None = None,
    is_complete: bool = True,
) -> UUID:
    tool_calls = build_spider_tool_calls(
        tool_trace=tool_trace,
        failure=failure,
        todos=todos,
    )
    if message_id is None:
        message = await session_service.add_message(
            session_id,
            MessageCreate(
                role=MessageRole.assistant,
                content=content,
                tool_calls=tool_calls,
                is_complete=is_complete,
            ),
        )
        return UUID(str(message.id))

    await session_service.update_message(
        message_id,
        content=content,
        tool_calls=tool_calls,
        is_complete=is_complete,
    )
    return message_id
