"""Resume-point computation for the deterministic spider pipeline.

A cancelled or failed pipeline leaves its stage artifacts in the session's
Docker volume. Resume re-enters at the first stage whose artifact is missing or
fails validation, reusing everything before it. Completion is decided by the
*same* validity checks the pipeline applies, so a half-written file from a
cancel is never trusted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.spider.services.code_guards import validate_spider_imports

PIPELINE_STAGE_COUNT = 4


class WorkspaceReader(Protocol):
    """Minimal read surface of ``SandboxWorkspace`` used for probing artifacts."""

    def read_text(self, filename: str) -> str | None: ...


@dataclass(frozen=True)
class StageCompletion:
    """Whether each pipeline stage's artifact exists and passes validation."""

    analysis_ready: bool = False  # stage 0: web_analyzer
    code_ready: bool = False  # stage 1: code_generator
    data_ready: bool = False  # stage 2: debug_agent
    validated: bool = False  # stage 3: data_processor


def resume_from_index(completion: StageCompletion) -> int:
    """First incomplete stage index (``0..PIPELINE_STAGE_COUNT``).

    Uses the longest completed *prefix*: because stages are sequential, a later
    stage is only trusted when every earlier stage is also complete. Returns
    ``PIPELINE_STAGE_COUNT`` when every stage is already done.
    """
    flags = (
        completion.analysis_ready,
        completion.code_ready,
        completion.data_ready,
        completion.validated,
    )
    for index, ready in enumerate(flags):
        if not ready:
            return index
    return PIPELINE_STAGE_COUNT


def probe_stage_completion(workspace: WorkspaceReader) -> StageCompletion:
    """Inspect a session workspace and decide which stages are already done."""
    analysis_report = workspace.read_text("analysis_report.json")
    analysis_ready = _is_json_object(analysis_report) and _non_empty(
        workspace.read_text("source_page.html")
    )

    spider_code = workspace.read_text("spider.py")
    code_ready = False
    if _non_empty(spider_code):
        result = validate_spider_imports(
            str(spider_code), scrape_engine=_scrape_engine_hint(analysis_report)
        )
        code_ready = bool(result.get("valid"))

    data_ready = (
        _count_records(workspace.read_text("raw_data.json")) > 0
        or _count_records(workspace.read_text("scraped_data.json")) > 0
    )

    validated = _non_empty(workspace.read_text("cleaned_data.json")) and _validation_passed(
        workspace.read_text("validation_report.json")
    )

    return StageCompletion(
        analysis_ready=analysis_ready,
        code_ready=code_ready,
        data_ready=data_ready,
        validated=validated,
    )


def _non_empty(text: str | None) -> bool:
    return bool(text and text.strip())


def _is_json_object(text: str | None) -> bool:
    if not text:
        return False
    try:
        return isinstance(json.loads(text), dict)
    except (TypeError, ValueError):
        return False


def _validation_passed(text: str | None) -> bool:
    if not text:
        return False
    try:
        report = json.loads(text)
    except (TypeError, ValueError):
        return False
    return isinstance(report, dict) and report.get("valid") is True


def _scrape_engine_hint(report_text: str | None) -> str:
    if not report_text:
        return "requests"
    try:
        report = json.loads(report_text)
    except (TypeError, ValueError):
        return "requests"
    engine = report.get("scrape_engine") if isinstance(report, dict) else None
    return engine if engine in {"requests", "playwright"} else "requests"


def _count_records(text: str | None) -> int:
    if not text or not text.strip():
        return 0
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return 0
    if isinstance(data, list):
        return sum(1 for item in data if item)
    if isinstance(data, dict):
        if data.get("error"):
            return 0
        return 1 if data else 0
    return 0
