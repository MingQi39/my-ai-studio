"""Connection-independent SSE task registry.

The generation task belongs to a user/session, not to a browser connection.
Subscribers may disconnect and later replay the buffered events before
following new events in real time.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

StreamFactory = Callable[[], AsyncIterator[dict[str, Any]]]


@dataclass
class ResumableStreamState:
    key: str
    metadata: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    is_active: bool = True
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    task: asyncio.Task[None] | None = None


class ResumableStreamManager:
    """Run one background producer per key and replay its events to subscribers."""

    def __init__(
        self,
        *,
        retention_seconds: int = 600,
        max_completed_streams: int = 100,
    ) -> None:
        self._streams: dict[str, ResumableStreamState] = {}
        self._retention = timedelta(seconds=retention_seconds)
        self._max_completed_streams = max_completed_streams

    async def start(
        self,
        key: str,
        stream_factory: StreamFactory,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ResumableStreamState:
        self._prune()
        existing = self._streams.get(key)
        if existing and existing.is_active:
            raise RuntimeError("A generation is already active for this session")

        state = ResumableStreamState(key=key, metadata=dict(metadata or {}))
        self._streams[key] = state
        state.task = asyncio.create_task(self._produce(state, stream_factory))
        return state

    def get(self, key: str) -> ResumableStreamState | None:
        self._prune()
        return self._streams.get(key)

    def status(self, key: str) -> dict[str, Any]:
        state = self.get(key)
        return {
            "is_streaming": bool(state and state.is_active),
            "event_count": len(state.events) if state else 0,
            "metadata": dict(state.metadata) if state else {},
        }

    async def cancel(self, key: str) -> bool:
        state = self.get(key)
        if state is None or not state.is_active or state.task is None:
            return False
        state.task.cancel()
        try:
            await state.task
        except asyncio.CancelledError:
            pass
        return True

    async def subscribe(
        self,
        key: str,
        *,
        after_event: int = 0,
    ) -> AsyncIterator[dict[str, Any]]:
        state = self.get(key)
        if state is None:
            raise KeyError(key)

        index = max(0, after_event)
        while True:
            async with state.condition:
                await state.condition.wait_for(
                    lambda: index < len(state.events) or not state.is_active
                )
                pending = state.events[index:]
                index = len(state.events)
                finished = not state.is_active

            for event in pending:
                yield event

            if finished and index >= len(state.events):
                break

    async def _produce(
        self,
        state: ResumableStreamState,
        stream_factory: StreamFactory,
    ) -> None:
        try:
            async for event in stream_factory():
                await self._publish(state, event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._publish(
                state,
                {
                    "type": "error",
                    "error_type": "background_stream_error",
                    "message": str(exc),
                    "recoverable": True,
                },
            )
            await self._publish(state, {"type": "done"})
        finally:
            async with state.condition:
                state.is_active = False
                state.completed_at = datetime.now(timezone.utc)
                state.condition.notify_all()

    async def _publish(
        self,
        state: ResumableStreamState,
        event: dict[str, Any],
    ) -> None:
        async with state.condition:
            state.events.append(dict(event))
            state.condition.notify_all()

    def _prune(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [
            key
            for key, state in self._streams.items()
            if not state.is_active
            and state.completed_at is not None
            and now - state.completed_at > self._retention
        ]
        for key in expired:
            self._streams.pop(key, None)

        completed = sorted(
            (
                state
                for state in self._streams.values()
                if not state.is_active and state.completed_at is not None
            ),
            key=lambda state: state.completed_at or state.started_at,
        )
        excess = len(completed) - self._max_completed_streams
        for state in completed[: max(0, excess)]:
            self._streams.pop(state.key, None)


def resumable_stream_key(kind: str, user_id: Any, session_id: Any) -> str:
    return f"{kind}:{user_id}:{session_id}"


resumable_stream_manager = ResumableStreamManager()
