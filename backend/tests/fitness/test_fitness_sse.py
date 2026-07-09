import json
from datetime import datetime, timezone

from app.api.v1.fitness import _json_dumps_sse


def test_json_dumps_sse_serializes_datetime_fields():
    payload = {
        "type": "tool_call_result",
        "result": {
            "daily_calorie_goal": 1600,
            "updated_at": datetime(2026, 7, 9, 2, 30, tzinfo=timezone.utc),
        },
    }

    encoded = _json_dumps_sse(payload)
    parsed = json.loads(encoded)

    assert parsed["result"]["daily_calorie_goal"] == 1600
    assert "2026-07-09" in parsed["result"]["updated_at"]
