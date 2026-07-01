"""Persist formal travel plans on travel sessions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.models.schemas import SessionUpdate
from app.models.database import SessionType
from app.services.session_service import SessionService
from app.travel.itinerary_models import (
    StructuredTravelPlan,
    TravelPlanGenerateResponse,
    TravelPlanStatusResponse,
)
from app.travel.services.itinerary_service import extract_latest_plan_from_messages

FORMAL_PLAN_SESSION_KEY = "travel_formal_plan"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def compute_plan_fingerprint(user_request: str, assistant_plan: str) -> str:
    return f"{user_request.strip()}::{assistant_plan.strip()[:120]}"


def _parse_session_description(description: str | None) -> dict[str, Any]:
    if not description:
        return {}
    try:
        data = json.loads(description)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _serialize_session_description(payload: dict[str, Any]) -> str | None:
    if not payload:
        return None
    return json.dumps(payload, ensure_ascii=False)


async def save_formal_plan(
    session_service: SessionService,
    session_id: UUID,
    user_id: UUID,
    *,
    fingerprint: str,
    response: TravelPlanGenerateResponse,
) -> None:
    session = await session_service.get_session(session_id, user_id)
    if not session:
        raise ValueError("Session not found")
    if session.session_type != SessionType.travel:
        raise ValueError("Not a travel session")

    payload = _parse_session_description(session.description)
    payload[FORMAL_PLAN_SESSION_KEY] = {
        "fingerprint": fingerprint,
        "generated_at": utc_now_iso(),
        "plan": response.plan.model_dump(),
        "markdown": response.markdown,
    }

    await session_service.update_session(
        session_id,
        user_id,
        SessionUpdate(description=_serialize_session_description(payload)),
    )


async def clear_formal_plan(
    session_service: SessionService,
    session_id: UUID,
    user_id: UUID,
) -> None:
    session = await session_service.get_session(session_id, user_id)
    if not session or not session.description:
        return

    payload = _parse_session_description(session.description)
    if FORMAL_PLAN_SESSION_KEY not in payload:
        return

    payload.pop(FORMAL_PLAN_SESSION_KEY, None)
    await session_service.update_session(
        session_id,
        user_id,
        SessionUpdate(description=_serialize_session_description(payload)),
    )


def _load_stored_formal_plan(description: str | None) -> dict[str, Any] | None:
    payload = _parse_session_description(description)
    stored = payload.get(FORMAL_PLAN_SESSION_KEY)
    return stored if isinstance(stored, dict) else None


async def get_formal_plan_status(
    session_service: SessionService,
    session_id: UUID,
    user_id: UUID,
) -> TravelPlanStatusResponse:
    session = await session_service.get_session(session_id, user_id)
    if not session:
        raise ValueError("Session not found")
    if session.session_type != SessionType.travel:
        raise ValueError("Not a travel session")

    stored = _load_stored_formal_plan(session.description)
    if not stored:
        return TravelPlanStatusResponse(exists=False)

    current = extract_latest_plan_from_messages(await session_service.get_messages(session_id))
    current_fingerprint = (
        compute_plan_fingerprint(current[0], current[1]) if current else None
    )
    stored_fingerprint = stored.get("fingerprint")
    is_stale = not current_fingerprint or current_fingerprint != stored_fingerprint

    try:
        plan = StructuredTravelPlan.model_validate(stored.get("plan", {}))
    except ValueError:
        return TravelPlanStatusResponse(exists=False)

    markdown = stored.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        return TravelPlanStatusResponse(exists=False)

    return TravelPlanStatusResponse(
        exists=True,
        is_stale=is_stale,
        fingerprint=stored_fingerprint if isinstance(stored_fingerprint, str) else None,
        generated_at=stored.get("generated_at") if isinstance(stored.get("generated_at"), str) else None,
        plan=plan,
        markdown=markdown,
    )
