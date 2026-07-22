"""TrainingAttempt state machine helpers (pure, DB-free)."""

from __future__ import annotations

from typing import Any

ACTIVE_STATUSES = frozenset({"open", "answering", "evaluated", "reanswered", "degraded"})
TERMINAL_STATUSES = frozenset({"committed", "abandoned"})

RULE_VERSION = "interview-eval-v1"


def can_submit_version(status: str, version: int) -> bool:
    if version == 1:
        return status in {"open", "degraded"}
    if version == 2:
        return status == "evaluated"
    return False


def can_commit(status: str, answers: list[dict[str, Any]], evaluation: dict[str, Any] | None) -> bool:
    if status == "reanswered":
        return True
    if status == "evaluated" and evaluation and evaluation.get("complete"):
        return True
    versions = {int(a.get("version", 0)) for a in answers}
    if 2 in versions and status in {"evaluated", "reanswered", "answering"}:
        return True
    return False


def can_abandon(status: str) -> bool:
    return status in ACTIVE_STATUSES


def after_answer_status(version: int) -> str:
    return "answering" if version == 1 else "reanswered"


def _norm_goal_level(value: str | None) -> str | None:
    """Normalize P5/P6/P7 and 初/中/高级 so snapshot vs profile compares fairly."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    mapping = {
        "P5": "初级",
        "P6": "中级",
        "P7": "高级",
        "初级": "初级",
        "中级": "中级",
        "高级": "高级",
    }
    return mapping.get(text, text)


def active_attempt_matches_goal(
    goal_snapshot: dict[str, Any] | None,
    *,
    target_role: str | None,
    target_level: str | None = None,
    salary_band: str | None = None,
) -> bool:
    """False when frozen attempt goal diverges from current profile — do not resume."""
    snap = goal_snapshot or {}
    snap_role = str(snap.get("target_role") or "").strip() or None
    role = (target_role or "").strip() or None
    if snap_role and role and snap_role != role:
        return False

    snap_level = _norm_goal_level(
        str(snap["target_level"]) if snap.get("target_level") is not None else None
    )
    level = _norm_goal_level(target_level)
    if snap_level and level and snap_level != level:
        return False

    snap_salary = str(snap.get("salary_band") or "").strip() or None
    salary = (salary_band or "").strip() or None
    if snap_salary and salary and snap_salary != salary:
        return False

    return True
