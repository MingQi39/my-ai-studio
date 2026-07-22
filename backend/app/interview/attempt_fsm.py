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
