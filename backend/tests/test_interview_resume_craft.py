"""Unit tests for interview resume craft (eligibility / draft / anti-fabrication)."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.interview.resume_craft import (
    _collect_metrics,
    build_polish_system_prompt,
    build_resume_draft,
    check_eligibility,
    load_style_examples,
    polish_or_template,
    render_template_markdown,
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
    assert draft["evidence_from_training"][0]["work_bucket"] == "trade-off"
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
    assert "技能关键词" in md
    assert "项目成果" in md
    assert "待补充数据" in md
    assert "未经验证" in md
    assert "300%" not in md


def test_template_markdown_groups_work_buckets():
    draft = {
        "profile": {"target_role": "后端", "target_level": "P6", "salary_band": None, "keywords": []},
        "claims": [{"id": "1", "category": "project", "label": "网关", "keywords": ["Go"]}],
        "evidence_from_training": [
            {
                "attempt_id": "a1",
                "topic": "限流",
                "focus_node": "Trade-off",
                "work_bucket": "trade-off",
                "source_claim_ids": ["1"],
                "user_answer_excerpts": ["选用令牌桶因为平滑突发"],
                "covered_nodes": ["Trade-off"],
                "evaluation_flags": {},
            },
            {
                "attempt_id": "a2",
                "topic": "观测",
                "focus_node": "Evidence",
                "work_bucket": "evidence",
                "source_claim_ids": ["1"],
                "user_answer_excerpts": ["用延迟直方图验证尾延迟"],
                "covered_nodes": ["Evidence"],
                "evaluation_flags": {},
            },
        ],
        "constraints": [],
    }
    md = render_template_markdown(draft)
    assert "取舍与方案" in md
    assert "证据与验证" in md
    assert "技术栈" in md
    assert "限流" in md


def test_style_examples_have_no_metrics():
    text = load_style_examples()
    assert text
    assert _collect_metrics(text) == set()


def test_polish_system_prompt_includes_skeleton_and_examples():
    prompt = build_polish_system_prompt()
    assert "项目成果" in prompt
    assert "示例·工业知识库" in prompt
    assert "禁止" in prompt


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
                "work_bucket": "evidence",
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
