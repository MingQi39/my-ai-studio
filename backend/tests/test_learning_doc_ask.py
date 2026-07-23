"""Tests for learning-doc quote ask."""

import pytest

from app.interview.learning_doc_ask import ask_about_learning_quote
from app.interview.schemas import LearningDocAskRequest


@pytest.mark.asyncio
async def test_ask_fallback_without_llm(monkeypatch):
    async def _none(**kwargs):
        return None

    monkeypatch.setattr(
        "app.interview.learning_doc_ask._call_ask_llm",
        _none,
    )
    result = await ask_about_learning_quote(
        LearningDocAskRequest(
            quote="自注意力允许每个 token 看见全局",
            question="面试怎么答？",
            topic="LLM",
            section_title="Transformer",
        )
    )
    assert result.generated_by == "template"
    assert "自注意力" in result.answer
    assert result.question == "面试怎么答？"


@pytest.mark.asyncio
async def test_ask_rejects_short_quote():
    with pytest.raises(ValueError):
        await ask_about_learning_quote(LearningDocAskRequest(quote="a", question="x"))
