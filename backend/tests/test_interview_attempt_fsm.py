"""Unit tests for TrainingAttempt FSM and evaluation traces."""

from app.interview.attempt_fsm import (
    active_attempt_matches_goal,
    can_abandon,
    can_commit,
    can_submit_version,
)
from app.interview.training import evaluate_answer


def test_submit_version_gates():
    assert can_submit_version("open", 1)
    assert can_submit_version("degraded", 1)
    assert not can_submit_version("evaluated", 1)
    assert can_submit_version("evaluated", 2)
    assert not can_submit_version("reanswered", 2)
    assert not can_submit_version("committed", 1)


def test_commit_requires_v2_or_complete():
    assert not can_commit("evaluated", [{"version": 1}], {"complete": False})
    assert can_commit("evaluated", [{"version": 1}], {"complete": True})
    assert can_commit("reanswered", [{"version": 1}, {"version": 2}], {"complete": False})
    assert not can_abandon("committed")
    assert can_abandon("evaluated")


def test_evaluate_includes_signals_hit():
    result = evaluate_answer("SSE 用来推消息", focus_node="Trade-off")
    assert "signals_hit" in result
    assert "Position" in result["signals_hit"]


def test_resume_blocked_when_target_role_changes():
    """全栈出题后再改 AI 应用工程，不得 resume 旧 attempt。"""
    snap = {
        "target_role": "全栈",
        "target_level": "中级",
        "salary_band": "25-40k",
    }
    assert active_attempt_matches_goal(
        snap,
        target_role="全栈",
        target_level="中级",
        salary_band="25-40k",
    )
    assert not active_attempt_matches_goal(
        snap,
        target_role="AI 应用工程",
        target_level="中级",
        salary_band="25-40k",
    )


def test_resume_blocked_when_level_or_salary_changes():
    snap = {
        "target_role": "全栈",
        "target_level": "中级",
        "salary_band": "25-40k",
    }
    assert not active_attempt_matches_goal(
        snap,
        target_role="全栈",
        target_level="高级",
        salary_band="25-40k",
    )
    assert not active_attempt_matches_goal(
        snap,
        target_role="全栈",
        target_level="P7",
        salary_band="25-40k",
    )
    assert not active_attempt_matches_goal(
        snap,
        target_role="全栈",
        target_level="中级",
        salary_band="40-60k",
    )
    # P6 ↔ 中级 should still match
    assert active_attempt_matches_goal(
        snap,
        target_role="全栈",
        target_level="P6",
        salary_band="25-40k",
    )
