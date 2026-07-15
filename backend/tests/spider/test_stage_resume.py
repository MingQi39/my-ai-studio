"""Unit tests for spider pipeline resume-point computation."""

from __future__ import annotations

import json

from app.spider.services.stage_resume import (
    PIPELINE_STAGE_COUNT,
    StageCompletion,
    probe_stage_completion,
    resume_from_index,
)


class FakeWorkspace:
    """Duck-typed workspace returning canned file contents."""

    def __init__(self, files: dict[str, str]):
        self._files = files

    def read_text(self, filename: str) -> str | None:
        return self._files.get(filename)


_VALID_SPIDER = "import json\nimport requests\nfrom bs4 import BeautifulSoup\n"
_ANALYSIS_REPORT = json.dumps({"analysis": "{}", "scrape_engine": "requests"})


def test_resume_from_index_all_incomplete_is_zero():
    assert resume_from_index(StageCompletion()) == 0


def test_resume_from_index_all_complete_is_stage_count():
    completion = StageCompletion(
        analysis_ready=True, code_ready=True, data_ready=True, validated=True
    )
    assert resume_from_index(completion) == PIPELINE_STAGE_COUNT


def test_resume_from_index_returns_first_gap():
    completion = StageCompletion(analysis_ready=True, code_ready=False)
    assert resume_from_index(completion) == 1


def test_resume_from_index_uses_completed_prefix_not_later_islands():
    # data_ready True but code_ready False: sequential prefix stops at the gap.
    completion = StageCompletion(
        analysis_ready=True, code_ready=False, data_ready=True, validated=True
    )
    assert resume_from_index(completion) == 1


def test_resume_from_index_data_processor_only():
    completion = StageCompletion(
        analysis_ready=True, code_ready=True, data_ready=True, validated=False
    )
    assert resume_from_index(completion) == 3


def test_probe_empty_workspace_is_all_false():
    completion = probe_stage_completion(FakeWorkspace({}))
    assert completion == StageCompletion()


def test_probe_marks_analysis_ready_when_report_and_source_present():
    completion = probe_stage_completion(
        FakeWorkspace(
            {
                "analysis_report.json": _ANALYSIS_REPORT,
                "source_page.html": "<html>hi</html>",
            }
        )
    )
    assert completion.analysis_ready is True
    assert completion.code_ready is False


def test_probe_analysis_not_ready_when_source_page_empty():
    completion = probe_stage_completion(
        FakeWorkspace({"analysis_report.json": _ANALYSIS_REPORT, "source_page.html": "   "})
    )
    assert completion.analysis_ready is False


def test_probe_code_ready_only_when_imports_valid():
    ready = probe_stage_completion(
        FakeWorkspace(
            {
                "analysis_report.json": _ANALYSIS_REPORT,
                "source_page.html": "<html/>",
                "spider.py": _VALID_SPIDER,
            }
        )
    )
    assert ready.code_ready is True


def test_probe_code_not_ready_when_half_written():
    broken = probe_stage_completion(
        FakeWorkspace(
            {
                "analysis_report.json": _ANALYSIS_REPORT,
                "source_page.html": "<html/>",
                "spider.py": "def main(:",  # syntax error from a cancel mid-write
            }
        )
    )
    assert broken.code_ready is False


def test_probe_data_ready_from_records():
    completion = probe_stage_completion(
        FakeWorkspace({"scraped_data.json": json.dumps([{"title": "a"}])})
    )
    assert completion.data_ready is True


def test_probe_data_not_ready_when_empty_list():
    completion = probe_stage_completion(FakeWorkspace({"scraped_data.json": "[]"}))
    assert completion.data_ready is False


def test_probe_validated_requires_cleaned_and_report_valid():
    completion = probe_stage_completion(
        FakeWorkspace(
            {
                "cleaned_data.json": json.dumps([{"title": "a"}]),
                "validation_report.json": json.dumps({"valid": True}),
            }
        )
    )
    assert completion.validated is True


def test_probe_not_validated_when_report_invalid():
    completion = probe_stage_completion(
        FakeWorkspace(
            {
                "cleaned_data.json": json.dumps([{"title": "a"}]),
                "validation_report.json": json.dumps({"valid": False}),
            }
        )
    )
    assert completion.validated is False


def test_probe_full_completion_resumes_at_stage_count():
    completion = probe_stage_completion(
        FakeWorkspace(
            {
                "analysis_report.json": _ANALYSIS_REPORT,
                "source_page.html": "<html/>",
                "spider.py": _VALID_SPIDER,
                "scraped_data.json": json.dumps([{"title": "a"}]),
                "cleaned_data.json": json.dumps([{"title": "a"}]),
                "validation_report.json": json.dumps({"valid": True}),
            }
        )
    )
    assert resume_from_index(completion) == PIPELINE_STAGE_COUNT
