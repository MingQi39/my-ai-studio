"""Tests for learning source catalog and daily doc template fallback."""

from datetime import date
from types import SimpleNamespace

import pytest

from app.interview.daily_doc_generator import (
    _section_keywords,
    _stem_relevance,
    generate_daily_learning_doc,
    push_message_for_doc,
)
from app.interview.learning_sources import format_source_links, handbooks_for_topic
from app.interview.model_roles import resolve_model_role
from app.interview.schemas import PlanDayTask


@pytest.mark.asyncio
async def test_template_ignores_mismatched_bank_stems(monkeypatch):
    async def _bad_stems(*args, **kwargs):
        return [
            "用 LLM 给 LLM 打分有什么坑？",
            "Few-shot 示例顺序会影响结果吗？",
            "大模型应用中常见的幻觉有哪些类型？",
        ]

    monkeypatch.setattr(
        "app.interview.daily_doc_generator.gather_reference_stems",
        _bad_stems,
    )

    async def _no_llm(_prompt):
        return None

    monkeypatch.setattr(
        "app.interview.daily_doc_generator._call_daily_doc_llm",
        _no_llm,
    )

    profile = SimpleNamespace(
        target_role="AI 应用工程",
        target_level="中级",
        salary_band="25-40k",
        target_deadline=date(2026, 12, 1),
    )
    task = PlanDayTask(
        date="2026-07-22",
        task_type="train",
        stage_id="s1_llm_prompt",
        title="大模型与 Prompt 工程",
        topic="LLM",
        goal="Transformer / Token 直觉",
        message="",
        doc_title="大模型与 Prompt 工程",
        section_title="Transformer 与注意力机制",
        reading_bullets=[
            "自注意力：每个 token 对序列中其他 token 计算权重",
            "Q/K/V 投影：Query 查、Key 被匹配、Value 提供内容",
        ],
    )
    doc = await generate_daily_learning_doc(None, profile=profile, task=task)  # type: ignore[arg-type]
    assert doc.generated_by == "template"
    assert "自注意力" in doc.markdown_body
    assert "用 LLM 给 LLM 打分" not in doc.markdown_body
    assert "幻觉有哪些类型" not in doc.markdown_body
    assert "](http" in doc.markdown_body
    assert "**对照**" in doc.markdown_body
    assert "打开下方参考链接中与「Transformer" not in doc.markdown_body


def test_handbooks_for_rag_topic():
    refs = handbooks_for_topic("RAG")
    assert any("RAG" in r.title for r in refs)


def test_github_files_for_stage():
    links = format_source_links("s2_rag", "RAG")
    assert any("RAG" in l["title"] or "03-RAG" in l["title"] for l in links)
    assert any("github.com" in l["url"] for l in links)


@pytest.mark.asyncio
async def test_template_fallback_without_llm(monkeypatch):
    async def _empty_stems(*args, **kwargs):
        return []

    monkeypatch.setattr(
        "app.interview.daily_doc_generator.gather_reference_stems",
        _empty_stems,
    )
    async def _no_llm(_prompt):
        return None

    monkeypatch.setattr(
        "app.interview.daily_doc_generator._call_daily_doc_llm",
        _no_llm,
    )

    profile = SimpleNamespace(
        target_role="AI 应用工程",
        target_level="中级",
        salary_band="25-40k",
        target_deadline=date(2026, 12, 1),
    )
    task = PlanDayTask(
        date="2026-07-22",
        task_type="train",
        stage_id="s2_rag",
        title="RAG 技术",
        topic="RAG",
        goal="分块、检索、重排",
        message="",
        doc_title="RAG 技术",
        section_title="文档分块",
        reading_bullets=["要点一", "要点二"],
    )
    doc = await generate_daily_learning_doc(None, profile=profile, task=task)  # type: ignore[arg-type]
    assert doc.generated_by == "template"
    assert doc.format_version == "qa_v1"
    assert doc.markdown_body
    assert "## 知识讲解" in doc.markdown_body
    assert "## 面试题与详解" in doc.markdown_body
    assert "**答案**" in doc.markdown_body
    assert "**讲解**" in doc.markdown_body
    teaser = push_message_for_doc(doc)
    assert "点击打开" in teaser or "完整答案" in teaser
    # Template Qs must follow today's bullets, not unrelated bank stems.
    assert "请用面试口述讲清：要点一" in doc.markdown_body
    assert "用 LLM 给 LLM 打分" not in doc.markdown_body


def test_daily_doc_model_inherits_hint(monkeypatch):
    monkeypatch.setattr("app.interview.model_roles.settings.INTERVIEW_DAILY_DOC_MODEL", "")
    monkeypatch.setattr("app.interview.model_roles.settings.INTERVIEW_DAILY_DOC_PROVIDER", "")
    monkeypatch.setattr("app.interview.model_roles.settings.INTERVIEW_HINT_MODEL", "deepseek-chat")
    monkeypatch.setattr(
        "app.interview.model_roles.settings.INTERVIEW_HINT_PROVIDER", "openai_compatible"
    )
    role = resolve_model_role("daily_doc")
    assert role.model_id == "deepseek-chat"
    assert role.provider_hint == "openai_compatible"


def test_stem_relevance_prefers_section():
    keys = _section_keywords("Transformer 与注意力机制", "LLM")
    assert _stem_relevance("自注意力 QKV 怎么算", keys) > _stem_relevance(
        "用 LLM 给 LLM 打分有什么坑？", keys
    )
