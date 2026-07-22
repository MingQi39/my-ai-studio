"""Tests for learning path recommendations."""

from app.interview.learning_path import recommend_learning_path, comic_url_for_topic


def test_next_module_starts_at_llm_when_empty():
    path = recommend_learning_path(committed_topics=set(), role_topics=["LLM", "RAG", "Agent"])
    assert path["next_module"]["topic"] == "LLM"
    assert path["done_count"] == 0


def test_next_module_advances_after_llm_covered():
    path = recommend_learning_path(
        committed_topics={"LLM"},
        role_topics=["LLM", "RAG", "Agent", "Memory"],
    )
    assert path["next_module"]["topic"] == "RAG"


def test_comic_url_for_rag():
    assert comic_url_for_topic("RAG") == "/interview/comics/03-RAG流程.png"
