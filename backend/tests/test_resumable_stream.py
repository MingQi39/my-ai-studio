import asyncio

import pytest

from app.core.resumable_stream import ResumableStreamManager


@pytest.mark.asyncio
async def test_generation_continues_after_subscriber_disconnect_and_replays_events():
    release = asyncio.Event()
    manager = ResumableStreamManager()

    async def producer():
        yield {"type": "step", "content": "observe"}
        await release.wait()
        yield {"type": "chunk", "content": "answer"}
        yield {"type": "done"}

    await manager.start("travel:user:session", producer, metadata={"mode": "agent"})

    first = manager.subscribe("travel:user:session")
    assert await anext(first) == {"type": "step", "content": "observe"}
    await first.aclose()

    release.set()
    state = manager.get("travel:user:session")
    assert state is not None and state.task is not None
    await state.task

    replayed = [event async for event in manager.subscribe("travel:user:session")]
    assert replayed == [
        {"type": "step", "content": "observe"},
        {"type": "chunk", "content": "answer"},
        {"type": "done"},
    ]
    assert manager.status("travel:user:session") == {
        "is_streaming": False,
        "event_count": 3,
        "metadata": {"mode": "agent"},
    }


@pytest.mark.asyncio
async def test_rejects_second_active_generation_for_same_session():
    release = asyncio.Event()
    manager = ResumableStreamManager()

    async def producer():
        await release.wait()
        if False:
            yield {}

    state = await manager.start("fitness:user:session", producer)
    with pytest.raises(RuntimeError, match="already active"):
        await manager.start("fitness:user:session", producer)

    release.set()
    assert state.task is not None
    await state.task


@pytest.mark.asyncio
async def test_explicit_cancel_stops_background_generation():
    started = asyncio.Event()
    manager = ResumableStreamManager()

    async def producer():
        started.set()
        await asyncio.Event().wait()
        if False:
            yield {}

    await manager.start("spider:user:session", producer)
    await started.wait()

    assert await manager.cancel("spider:user:session") is True
    assert manager.status("spider:user:session")["is_streaming"] is False
