import asyncio
import json

import pytest

from app.travel.services.sse_merge import merge_streams


@pytest.mark.asyncio
async def test_merge_streams_delivers_all_events_from_both_sources():
    async def llm_stream():
        yield {"type": "start", "source": "llm"}
        yield {"type": "chunk", "source": "llm", "content": "hello"}
        yield {"type": "done", "source": "llm"}

    async def agent_stream():
        yield {"type": "start", "source": "agent"}
        yield {"type": "step", "source": "agent", "step_type": "Observe", "content": "obs"}
        yield {"type": "final_response", "source": "agent", "content": "plan"}
        yield {"type": "done", "source": "agent"}

    lines = [line async for line in merge_streams(llm_stream(), agent_stream())]
    assert len(lines) == 7

    events = []
    for line in lines:
        assert line.startswith("data: ")
        events.append(json.loads(line[6:]))

    types_by_source: dict[str, list[str]] = {"llm": [], "agent": []}
    for event in events:
        types_by_source[event["source"]].append(event["type"])

    assert types_by_source["llm"] == ["start", "chunk", "done"]
    assert types_by_source["agent"] == ["start", "step", "final_response", "done"]
