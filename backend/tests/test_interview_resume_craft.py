"""Unit tests for interview resume craft (eligibility / draft / anti-fabrication)."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.interview.resume_craft import (
    check_eligibility,
    build_resume_draft,
    render_template_markdown,
    extract_novel_metrics,
    polish_or_template,
)


def test_eligibility_requires_claims_and_recent_commit():
    claims = [
        SimpleNamespace(status="confirmed", category="skill", label="React", keywords=["React"], id="1"),
        SimpleNamespace(status="confirmed", category="skill", label="SSE", keywords=["SSE"], id="2"),
        SimpleNamespace(status="confirmed", category="project", label="Qi AI Studio", keywords=[], id="3"),
    ]
    bad = check_eligibility(confirmed_claims=claims[:1], committed_attempts_7d=0)
    assert bad["eligible"] is False
    assert bad["stats"]["confirmed_claims"] == 1
    assert any("确认" in r for r in bad["reasons"])

    ok = check_eligibility(confirmed_claims=claims, committed_attempts_7d=1)
    assert ok["eligible"] is True
    assert ok["reasons"] == []


def test_draft_excludes_candidate_claims_and_includes_evidence():
    profile = SimpleNamespace(
        target_role="AI 应用工程师",
        target_level="P6",
        salary_band="30-50k",
        keywords=["FastAPI"],
    )
    claims = [
        SimpleNamespace(id="c1", status="confirmed", category="project", label="面试导航", keywords=["SSE"]),
        SimpleNamespace(id="c2", status="candidate", category="skill", label="K8s", keywords=["K8s"]),
    ]
    now = datetime(2026, 7, 22, tzinfo=timezone.utc)
    attempt = SimpleNamespace(
        id="a1",
        status="committed",
        topic="SSE",
        focus_node="Trade-off",
        source_claim_ids=["c1"],
        updated_at=now - timedelta(days=1),
        answers=[{"version": 1, "text": "选 SSE 因为单向推送与 HTTP 栈一致"}],
        evaluation={"covered_nodes": ["Principle", "Trade-off", "Evidence"]},
    )
    draft = build_resume_draft(
        profile=profile,
        confirmed_claims=[c for c in claims if c.status == "confirmed"],
        committed_attempts=[attempt],
    )
    assert [c["id"] for c in draft["claims"]] == ["c1"]
    assert draft["evidence_from_training"][0]["topic"] == "SSE"
    assert "SSE" in draft["evidence_from_training"][0]["user_answer_excerpts"][0]


def test_template_markdown_contains_footer_and_no_fake_metrics():
    draft = {
        "profile": {"target_role": "后端", "target_level": "P6", "salary_band": None, "keywords": ["Go"]},
        "claims": [{"id": "1", "category": "project", "label": "网关", "keywords": ["Go"]}],
        "evidence_from_training": [],
        "constraints": [],
    }
    md = render_template_markdown(draft)
    assert "网关" in md
    assert "待验证" in md or "未经验证" in md
    assert "300%" not in md


def test_novel_metrics_rejected_falls_back_to_template():
    draft = {
        "profile": {"target_role": "后端", "target_level": "P6", "salary_band": None, "keywords": []},
        "claims": [{"id": "1", "category": "project", "label": "网关", "keywords": []}],
        "evidence_from_training": [],
        "constraints": [],
    }
    polished = "# 简历\n- 性能提升 300%\n"
    md, warnings = polish_or_template(draft=draft, polished=polished)
    assert "300%" not in md
    assert any("metric" in w for w in warnings)


def test_polish_accepts_when_metric_already_in_excerpt():
    draft = {
        "profile": {"target_role": "后端", "target_level": "P6", "salary_band": None, "keywords": []},
        "claims": [{"id": "1", "category": "project", "label": "网关", "keywords": []}],
        "evidence_from_training": [
            {
                "user_answer_excerpts": ["延迟从 200ms 降到 50ms"],
                "source_claim_ids": ["1"],
                "topic": "性能",
                "focus_node": "Evidence",
                "covered_nodes": ["Evidence"],
                "attempt_id": "a",
                "evaluation_flags": {},
            }
        ],
        "constraints": [],
    }
    polished = "- 将延迟从 200ms 降到 50ms\n"
    md, warnings = polish_or_template(draft=draft, polished=polished)
    assert "50ms" in md
    assert warnings == []
