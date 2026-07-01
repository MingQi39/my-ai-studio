"""Merge multiple async SSE event streams for compare mode."""

import asyncio
import json
from typing import AsyncIterator


async def merge_streams(
    llm_stream: AsyncIterator,
    agent_stream: AsyncIterator,
) -> AsyncIterator[str]:
    """Merge two async event streams into SSE lines (llm + agent in parallel)."""
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def pump(stream: AsyncIterator, source: str) -> None:
        try:
            async for event in stream:
                if isinstance(event, dict):
                    event["source"] = source
                    await queue.put(event)
        except Exception as exc:
            await queue.put({
                "type": "error",
                "source": source,
                "error_type": "stream_error",
                "message": f"{source} 流异常: {exc}",
                "recoverable": False,
            })
            await queue.put({
                "type": "done",
                "source": source,
                "stats": {"llm_calls": 0, "tool_calls": 0, "duration_ms": 0},
            })
        finally:
            await queue.put(None)

    pumps = [
        asyncio.create_task(pump(llm_stream, "llm")),
        asyncio.create_task(pump(agent_stream, "agent")),
    ]
    finished = 0

    try:
        while finished < 2:
            event = await queue.get()
            if event is None:
                finished += 1
                continue
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0)
    finally:
        for task in pumps:
            task.cancel()
        await asyncio.gather(*pumps, return_exceptions=True)
