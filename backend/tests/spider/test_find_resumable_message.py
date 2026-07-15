"""Unit tests for locating the resumable assistant message in a session."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from app.spider.services.chat_persistence import (
    SPIDER_META_KEY,
    find_resumable_assistant_message,
)

_BASE = datetime(2026, 7, 15, 10, 0, 0)


@dataclass
class FakeMessage:
    role: str
    id: UUID = field(default_factory=uuid4)
    is_complete: bool = True
    tool_calls: list[dict[str, Any]] | None = None
    created_at: datetime = _BASE


def _failure_meta() -> list[dict[str, Any]]:
    return [{"type": SPIDER_META_KEY, "failure": {"title": "boom"}}]


def test_returns_none_when_all_complete_and_no_failure():
    messages = [
        FakeMessage(role="user", created_at=_BASE),
        FakeMessage(role="assistant", is_complete=True, created_at=_BASE + timedelta(minutes=1)),
    ]
    assert find_resumable_assistant_message(messages) is None


def test_returns_incomplete_assistant_message():
    target = FakeMessage(
        role="assistant", is_complete=False, created_at=_BASE + timedelta(minutes=2)
    )
    messages = [FakeMessage(role="user", created_at=_BASE), target]
    assert find_resumable_assistant_message(messages) == target.id


def test_returns_failed_assistant_message():
    target = FakeMessage(
        role="assistant",
        is_complete=True,
        tool_calls=_failure_meta(),
        created_at=_BASE + timedelta(minutes=2),
    )
    messages = [FakeMessage(role="user", created_at=_BASE), target]
    assert find_resumable_assistant_message(messages) == target.id


def test_picks_newest_resumable_when_multiple():
    older = FakeMessage(
        role="assistant", is_complete=False, created_at=_BASE + timedelta(minutes=1)
    )
    newer = FakeMessage(
        role="assistant", is_complete=False, created_at=_BASE + timedelta(minutes=5)
    )
    # Deliberately out of order to prove sorting.
    messages = [newer, FakeMessage(role="user", created_at=_BASE), older]
    assert find_resumable_assistant_message(messages) == newer.id


def test_ignores_user_messages():
    messages = [FakeMessage(role="user", is_complete=False, created_at=_BASE)]
    assert find_resumable_assistant_message(messages) is None
