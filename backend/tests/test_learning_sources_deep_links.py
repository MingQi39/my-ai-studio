"""Tests for section → clickable primary reference links."""

from app.interview.learning_sources import (
    format_crosscheck_markdown,
    primary_reference_for_section,
)


def test_transformer_section_resolves_to_http_link():
    ref = primary_reference_for_section(
        "Transformer 与注意力机制", topic="LLM", stage_id="s1_llm_prompt"
    )
    assert ref is not None
    assert ref.url.startswith("http")
    assert "对照" not in ref.label


def test_rag_chunking_section_resolves():
    ref = primary_reference_for_section(
        "文档分块（Chunking）策略", topic="RAG", stage_id="s2_rag"
    )
    assert ref is not None
    assert "http" in ref.url


def test_unknown_section_falls_back_by_topic_handbook():
    ref = primary_reference_for_section("不存在的章节 xyz", topic="RAG", stage_id="s2_rag")
    assert ref is not None
    assert "feishu.cn" in ref.url or "github.com" in ref.url


def test_format_crosscheck_markdown_is_clickable():
    ref = primary_reference_for_section(
        "Transformer 与注意力机制", topic="LLM", stage_id="s1_llm_prompt"
    )
    line = format_crosscheck_markdown(ref, "Transformer 与注意力机制")
    assert line.startswith("- **对照**：")
    assert "](http" in line
    assert "Transformer 与注意力机制" in line


def test_format_crosscheck_markdown_fallback_without_ref():
    line = format_crosscheck_markdown(None, "今日阅读")
    assert "对照" in line
    assert "](http" not in line
    assert "参考链接" in line
