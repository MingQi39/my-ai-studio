"""Unit tests for route reflection (no full-answer generation)."""

import pytest

from app.interview.route_reflector import (
    RouteReflection,
    merge_rule_and_reflection,
    parse_reflection_json,
    rule_reflect,
)


def test_parse_reflection_json_strict_shape():
    raw = """{
      "covered": ["Position"],
      "missing": ["Trade-off", "Evidence"],
      "hallucinated_metrics": ["提升了 300%"],
      "min_hint": "补一句取舍，不要写完整范文",
      "model_answer": "这是不应该出现的范文"
    }"""
    parsed = parse_reflection_json(raw)
    assert parsed.covered == ["Position"]
    assert "Trade-off" in parsed.missing
    assert parsed.hallucinated_metrics == ["提升了 300%"]
    assert "范文" not in (parsed.min_hint or "")
    # model_answer must be stripped / ignored
    assert not hasattr(parsed, "model_answer") or getattr(parsed, "model_answer", None) is None


def test_rule_reflect_flags_suspicious_metrics():
    report = rule_reflect(
        answer="我们把延迟优化了 99.7%，QPS 提升了 500 倍，准确率达到 100%。",
        focus_node="Evidence",
    )
    assert report.hallucinated_metrics
    assert report.min_hint


def test_merge_prefers_reflection_missing_but_keeps_rule_coverage():
    rule = {
        "covered_nodes": ["Position"],
        "missing_nodes": ["Mechanism", "Trade-off", "Evidence"],
        "breakpoint": "Mechanism",
        "hint": {"node": "Mechanism", "recall": "r", "keywords": "k", "example": "e"},
        "next_step": "补 Mechanism",
        "complete": False,
        "signals_hit": {"Position": ["用来"]},
    }
    reflection = RouteReflection(
        covered=["Position", "Mechanism"],
        missing=["Trade-off", "Evidence"],
        hallucinated_metrics=["500 倍"],
        min_hint="先说清楚和 WebSocket 比的代价",
    )
    merged = merge_rule_and_reflection(rule, reflection)
    assert "Mechanism" in merged["covered_nodes"]
    assert merged["breakpoint"] == "Trade-off"
    assert merged["llm"]["hallucinated_metrics"] == ["500 倍"]
    assert merged["llm"]["source"] == "route_reflection"
    assert "500" not in str(merged.get("hint", {}).get("example", ""))


@pytest.mark.asyncio
async def test_llm_reflect_rejects_answer_leak(monkeypatch):
    from app.interview.route_reflector import llm_reflect

    class FakeLLM:
        async def acomplete(self, messages, **kwargs):
            return '{"covered":["Position"],"missing":["Evidence"],"hallucinated_metrics":[],"min_hint":"补证据","full_answer":"SSE是...完整答案"}'

    report = await llm_reflect(
        llm=FakeLLM(),
        question="SSE vs WebSocket",
        answer="SSE 用来推消息",
        route_nodes=["Position", "Mechanism", "Trade-off", "Evidence"],
        focus_node="Trade-off",
    )
    assert report.missing == ["Evidence"]
    assert "完整答案" not in (report.min_hint or "")
