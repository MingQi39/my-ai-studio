"""Unit tests for contextual interview hints."""

from app.interview.contextual_hint import (
    build_hint_messages,
    has_submitted_evaluation,
    latest_answer_text,
    looks_like_boilerplate,
    looks_like_full_answer,
    resolve_contextual_hint,
    topic_template_hint,
)


def test_has_submitted_evaluation():
    assert has_submitted_evaluation(answers=None, evaluation=None) is False
    assert has_submitted_evaluation(answers=[{"version": 1, "text": "x"}], evaluation=None) is False
    assert has_submitted_evaluation(answers=[], evaluation={"breakpoint": "Position"}) is False
    assert (
        has_submitted_evaluation(
            answers=[{"version": 1, "text": "答"}],
            evaluation={"breakpoint": "Position"},
        )
        is True
    )


def test_all_levels_avoid_route_scaffolds_and_canned_clues():
    question = "请说明 MCP 协议的核心原理、优势及在 AI 工具调用中的应用流程"
    banned = (
        "适用场景",
        "问题边界",
        "谁受益",
        "组织骨架",
        "可用线索",
        "先补：",
        "当前先补",
        "解决什么问题",
        "它解决的是哪一类问题、在什么边界内成立",
    )
    for level in (1, 2, 3, 4):
        h = topic_template_hint(topic="MCP", node="Position", level=level, question=question)
        for b in banned:
            assert b not in h["content"], f"L{level} still has {b!r}: {h['content']}"
        assert "MCP" in h["content"] or "AI" in h["content"] or "应用流程" in h["content"]


def test_l3_keywords_from_question_only():
    question = "请说明 MCP 协议的核心原理、优势及在 AI 工具调用中的应用流程"
    h = topic_template_hint(topic="MCP", node="Position", level=3, question=question)
    assert "MCP" in h["content"]
    assert "适用场景" not in h["content"]


def test_boilerplate_llm_falls_back():
    payload, source = resolve_contextual_hint(
        topic="MCP",
        node="Position",
        level=3,
        llm_text="可用线索：适用场景 · 问题边界 · 谁受益",
        question="MCP 协议的核心原理是什么？",
    )
    assert source == "template"
    assert "适用场景" not in payload["content"]
    assert looks_like_boilerplate("先补：解决什么问题") is True


def test_llm_leak_falls_back_to_question_only_template():
    q = "为什么流式聊天选 SSE 而不是 WebSocket？"
    payload, source = resolve_contextual_hint(
        topic="SSE",
        node="Position",
        level=4,
        llm_text="这是标准答案：SSE 是服务器推送……" + ("长" * 80),
        question=q,
    )
    assert source == "template"
    assert "SSE" in payload["content"] or "WebSocket" in payload["content"]
    assert "组织骨架" not in payload["content"]
    assert "解决什么问题" not in payload["content"]


def test_llm_short_ok_adopted():
    payload, source = resolve_contextual_hint(
        topic="SSE",
        node="Position",
        level=2,
        llm_text="围绕 SSE 推送场景，先自问：为什么不是 WebSocket？",
        question="SSE 解决哪类通信问题？",
    )
    assert source == "llm"
    assert "SSE" in payload["content"]


def test_looks_like_full_answer_bans_phrases():
    assert looks_like_full_answer("可以这样答：先说场景再说原理") is True
    assert looks_like_full_answer("先补场景边界") is False


def test_build_hint_messages_pre_submit_marks_no_answer():
    msgs = build_hint_messages(
        topic="Python",
        question="GIL 下怎么选？",
        answer="",
        breakpoint=None,
        covered_nodes=[],
        missing_nodes=[],
        level=1,
        focus_node="Position",
    )
    assert "尚未作答" in msgs[1]["content"]
    assert "GIL" in msgs[1]["content"]
    assert "必须紧扣" in msgs[1]["content"] or "禁止通用套话" in msgs[1]["content"]


def test_build_hint_messages_include_context_after_submit():
    msgs = build_hint_messages(
        topic="Python",
        question="GIL 下怎么选？",
        answer="我会用多进程",
        breakpoint="Trade-off",
        covered_nodes=["Position"],
        missing_nodes=["Trade-off"],
        level=2,
    )
    assert msgs[0]["role"] == "system"
    assert "Python" in msgs[1]["content"]
    assert "我会用多进程" in msgs[1]["content"]


def test_latest_answer_text_picks_highest_version():
    text = latest_answer_text(
        [
            {"version": 1, "text": "旧"},
            {"version": 2, "text": "新答"},
        ]
    )
    assert text == "新答"
