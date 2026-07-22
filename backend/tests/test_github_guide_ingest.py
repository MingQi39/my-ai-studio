"""Tests for GitHub AI Agent interview guide ingest."""

from app.interview.github_guide_ingest import (
    extract_from_guide_repo,
    extract_questions_from_guide_markdown,
)


SAMPLE = """
## 1.3 面试问题

**Q1：一句话说明什么是 AI Agent？**
**A：** 闭环系统。

**面试 Q2：为什么需要 RAG？**
**A：** 知识截止。

### Q3: 为什么选择 ReAct 模式而不是 Plan-and-Execute？

- **追问：Agent 的「自主」是不是不受控？**
- **追问：为什么？**
"""


def test_extract_q_and_followups():
    items = extract_questions_from_guide_markdown(SAMPLE, default_topic="Agent")
    stems = [i.normalized_question for i in items]
    assert "一句话说明什么是 AI Agent？" in stems
    assert "为什么需要 RAG？" in stems
    assert "为什么选择 ReAct 模式而不是 Plan-and-Execute？" in stems
    assert "Agent 的「自主」是不是不受控？" in stems
    assert all("为什么？" != s for s in stems)


def test_topic_inference_rag():
    items = extract_questions_from_guide_markdown(
        "**Q1：分块太大或太小对 RAG 有什么影响？**\n",
        default_topic="Agent",
    )
    assert items[0].topic == "RAG"


def test_extract_from_cloned_repo():
    from pathlib import Path

    root = Path("/tmp/ai-agent-interview-guide")
    if not root.exists():
        return
    items = extract_from_guide_repo(root)
    assert len(items) >= 200
    topics = {i.topic for i in items}
    assert "RAG" in topics
    assert "Agent" in topics
    assert "LLM" in topics
