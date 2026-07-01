"""Tests for formal travel plan persistence."""

import json

from app.travel.itinerary_models import StructuredTravelPlan, TravelPlanGenerateResponse
from app.travel.services.formal_plan_storage import (
    FORMAL_PLAN_SESSION_KEY,
    _load_stored_formal_plan,
    _parse_session_description,
    compute_plan_fingerprint,
)


def test_compute_plan_fingerprint():
    fp = compute_plan_fingerprint("规划成都4日游", "Day1 春熙路 Day2 宽窄巷子")
    assert fp.startswith("规划成都4日游::")


def test_parse_and_load_formal_plan_from_description():
    stored = {
        "fingerprint": "abc",
        "generated_at": "2026-01-01T00:00:00Z",
        "plan": {
            "title": "成都美食之旅",
            "destination": "成都",
            "summary": "测试",
            "daily_itinerary": [],
            "accommodations": [],
            "transport": [],
            "budget_breakdown": [],
            "tips": [],
            "data_verified": False,
        },
        "markdown": "# 成都美食之旅",
    }
    description = json.dumps({FORMAL_PLAN_SESSION_KEY: stored}, ensure_ascii=False)
    payload = _parse_session_description(description)
    assert FORMAL_PLAN_SESSION_KEY in payload
    loaded = _load_stored_formal_plan(description)
    assert loaded is not None
    assert loaded["fingerprint"] == "abc"


def test_travel_plan_generate_response_defaults():
    plan = StructuredTravelPlan(
        title="测试",
        destination="成都",
        summary="概览",
    )
    response = TravelPlanGenerateResponse(plan=plan, markdown="# 测试")
    assert response.exists is True
    assert response.is_stale is False
