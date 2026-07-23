"""Background loop to mark interview daily pushes as due."""

from __future__ import annotations

import asyncio
import logging

from app.db.database import async_session_factory
from app.interview.plan_service import process_due_pushes

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60
_task: asyncio.Task | None = None


async def _push_loop() -> None:
    while True:
        try:
            async with async_session_factory() as db:
                count = await process_due_pushes(db)
                if count:
                    logger.info("Interview daily push marked", extra={"count": count})
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Interview push scheduler tick failed")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


def start_interview_push_scheduler() -> asyncio.Task:
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_push_loop(), name="interview-push-scheduler")
    return _task


async def stop_interview_push_scheduler() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
