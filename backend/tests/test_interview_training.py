"""Unit tests for Interview Navigator training helpers."""

from app.interview.training import (
    build_training_prompt,
    evaluate_answer,
    hint_for,
    normalize_level,
    pick_starter_topic,
    topics_for_role,
)


def test_starter_topic_without_resume():
    assert pick_starter_topic(set(), role="前端") == "React"
    assert pick_starter_topic({"React", "TypeScript"}, role="前端") == "组件设计"


def test_role_bank_and_difficulty_mapping():
    assert "RAG" in topics_for_role("AI 应用工程")
    assert "Python" in topics_for_role("AI 应用工程")
    assert normalize_level("高级") == "P7"
    assert normalize_level("中级") == "P6"


def test_goal_aware_question():
    prompt = build_training_prompt(
        topic="SSE",
        category="skill",
        level="P6",
        role="全栈",
        difficulty="中级",
        salary_band="40-60k",
    )
    # Goal stays in profile/UI; stem must be concrete (named alternative), not empty shell.
    assert "WebSocket" in prompt.question
    assert "相关场景选" not in prompt.question
    assert "期望水平" not in prompt.question
    assert prompt.focus_node == "Trade-off"


def test_rag_question_names_real_alternatives():
    prompt = build_training_prompt(
        topic="RAG",
        category="skill",
        level="P6",
        role="AI 应用工程",
        difficulty="中级",
        salary_band="40-60k",
    )
    assert "Fine-tuning" in prompt.question or "长上下文" in prompt.question
    assert "RAG" in prompt.question
    assert "更常见的替代方案" not in prompt.question
    assert prompt.focus_node == "Trade-off"


def test_project_from_resume_keeps_goal_context():
    prompt = build_training_prompt(
        topic="Qi AI Studio",
        category="project",
        role="AI 应用工程",
        difficulty="高级",
        salary_band="60k+",
    )
    assert "Qi AI Studio" in prompt.question
    assert "取舍" in prompt.question
    assert prompt.focus_node == "Evidence"


def test_sse_atlas_and_focus():
    prompt = build_training_prompt(topic="SSE", category="skill", level="P6")
    assert prompt.atlas[:3] == ["HTTP", "streaming", "SSE"]
    assert prompt.focus_node == "Trade-off"


def test_evaluate_detects_tradeoff_breakpoint():
    result = evaluate_answer("SSE 用来推消息", focus_node="Trade-off")
    assert result["breakpoint"] == "Trade-off"
    assert "Position" in result["covered_nodes"]
    assert result["complete"] is False


def test_evaluate_complete_path():
    answer = (
        "用来解决服务端推送问题，原理是单向通道，怎么实现靠 HTTP 流式写入，"
        "取舍是不选 WebSocket，我们项目里做过流式聊天"
    )
    result = evaluate_answer(answer)
    assert result["complete"] is True
    assert result["breakpoint"] is None


def test_progressive_hint_levels():
    assert "断点" in hint_for("Trade-off", 1)["content"]
    assert "为什么" in hint_for("Trade-off", 2)["content"]
