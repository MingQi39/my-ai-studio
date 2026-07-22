"""Unit tests for interview training progress metrics."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.interview.progress import (
    band_tier,
    build_progress_payload,
    compute_composite_score,
    compute_coverage,
    compute_route_depth,
    compute_weekly_trend,
    suggest_next_step,
    build_expectations,
)


def test_coverage_counts_committed_topics_only():
    cov = compute_coverage(
        role_topics=["LLM", "RAG", "SSE"],
        committed_topics={"RAG", "Docker"},
    )
    assert cov["covered_count"] == 1
    assert cov["missing_topics"] == ["LLM", "SSE"]
    assert cov["ratio"] == round(1 / 3, 4)


def test_route_depth_only_recent_window():
    now = datetime(2026, 7, 22, tzinfo=timezone.utc)
    recent = SimpleNamespace(
        updated_at=now - timedelta(days=1),
        evaluation={"covered_nodes": ["Position", "Trade-off"]},
    )
    old = SimpleNamespace(
        updated_at=now - timedelta(days=30),
        evaluation={"covered_nodes": ["Evidence"]},
    )
    depth = compute_route_depth(committed_attempts=[recent, old], now=now, window_days=7)
    assert depth["committed_count"] == 1
    assert depth["tradeoff_hits"] == 1
    assert depth["evidence_hits"] == 0


def test_mid_tier_expectations_and_next_step():
    coverage = {"covered_count": 1, "total_count": 6, "ratio": 1 / 6, "missing_topics": ["RAG"]}
    depth = {
        "committed_count": 2,
        "tradeoff_rate": 0.0,
        "evidence_rate": 0.0,
        "avg_covered_nodes": 2.0,
    }
    retention = {"due_count": 0, "consolidated_count": 0, "stuck_count": 0, "healthy_ratio": 0.0}
    ex = build_expectations(tier="mid", coverage=coverage, depth=depth, retention=retention)
    assert any(not e.met and e.id == "tradeoff_stable" for e in ex)
    step = suggest_next_step(coverage=coverage, depth=depth, retention=retention, expectations=ex)
    assert "取舍" in step or "覆盖" in step


def test_high_tier_caps_composite_without_evidence():
    score = compute_composite_score(
        coverage={"ratio": 1.0},
        depth={"tradeoff_rate": 1.0, "evidence_rate": 0.0, "avg_covered_nodes": 5},
        retention={"healthy_ratio": 1.0},
        tier="high",
    )
    assert score["score"] <= 68
    assert score["cap_reason"]


def test_weekly_trend_buckets():
    now = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)  # Wednesday
    a = SimpleNamespace(
        updated_at=now - timedelta(days=1),
        evaluation={"covered_nodes": ["Trade-off"]},
    )
    trend = compute_weekly_trend(committed_attempts=[a], weeks=2, now=now)
    assert len(trend) == 2
    assert trend[-1]["committed_count"] >= 1


def test_band_tier_from_salary_and_level():
    assert band_tier("60k+", "中级") == "high"
    assert band_tier("25-40k", "中级") == "mid"
    assert band_tier("15-25k", "初级") == "low"


def test_build_progress_payload_shape():
    now = datetime(2026, 7, 22, tzinfo=timezone.utc)
    attempt = SimpleNamespace(
        topic="RAG",
        updated_at=now,
        evaluation={"covered_nodes": ["Position", "Trade-off"]},
    )
    card = SimpleNamespace(
        missing_nodes=["Evidence"],
        successful_recall_count=0,
        next_due_at=now - timedelta(hours=1),
        status="new",
    )
    payload = build_progress_payload(
        target_role="AI 应用工程",
        target_level="中级",
        salary_band="25-40k",
        role_topics=["LLM", "RAG", "SSE"],
        committed_attempts=[attempt],
        cards=[card],
        now=now,
    )
    assert payload["goal"]["tier"] == "mid"
    assert payload["coverage"]["covered_count"] == 1
    assert payload["next_step"]
    assert "score" in payload["composite"]
    assert len(payload["weekly_trend"]) == 6
    assert payload["expectations"]
    assert payload["learning_path"]["next_module"]["topic"]
    assert payload["learning_path"]["total_relevant"] >= 1
