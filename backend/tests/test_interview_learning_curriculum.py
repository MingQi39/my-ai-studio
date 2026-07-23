"""Tests for curated learning curriculum attached to daily plans."""

from datetime import date, timedelta

from app.interview.learning_curriculum import format_learning_doc_message, reading_unit_for_day
from app.interview.learning_path import plan_from_deadline


def test_reading_unit_has_bullets():
    doc_title, section, bullets = reading_unit_for_day("s2_rag", task_type="train", day_index_in_stage=0)
    assert doc_title == "RAG 技术"
    assert section
    assert len(bullets) >= 2


def test_plan_day_includes_learning_doc_fields():
    start = date(2026, 5, 1)
    plan = plan_from_deadline(
        start_date=start,
        deadline=start + timedelta(days=9),
        committed_topics=set(),
        role_topics=["LLM", "RAG"],
    )
    day = plan["days"][0]
    assert day["doc_title"]
    assert day["section_title"]
    assert day["reading_bullets"]
    assert day["message"].startswith("📖")


def test_format_learning_doc_message_multiline():
    msg = format_learning_doc_message("RAG 技术", "分块策略", ("要点一", "要点二"))
    assert "📖 RAG 技术" in msg
    assert "· 要点一" in msg
