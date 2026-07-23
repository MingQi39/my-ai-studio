"""Tests for deadline-based learning plan generation."""

from datetime import date, timedelta

from app.interview.learning_path import plan_from_deadline, today_plan_tasks


def test_plan_from_deadline_allocates_all_days():
    start = date(2026, 1, 1)
    deadline = start + timedelta(days=29)
    plan = plan_from_deadline(
        start_date=start,
        deadline=deadline,
        committed_topics=set(),
        role_topics=["LLM", "RAG", "Agent"],
    )
    assert plan["total_days"] == 30
    assert len(plan["days"]) == 30
    assert plan["feasible"] is True
    assert plan["days"][0]["topic"] == "LLM"
    assert plan["days"][0]["task_type"] == "train"


def test_plan_skips_completed_stages():
    start = date(2026, 2, 1)
    deadline = start + timedelta(days=13)
    plan = plan_from_deadline(
        start_date=start,
        deadline=deadline,
        committed_topics={"LLM"},
        role_topics=["LLM", "RAG", "Agent"],
    )
    topics = {day["topic"] for day in plan["days"]}
    assert "LLM" not in topics or all(day["task_type"] == "consolidate" for day in plan["days"] if day["topic"] == "LLM")
    assert "RAG" in topics


def test_plan_past_deadline_is_not_feasible():
    start = date(2026, 3, 10)
    deadline = date(2026, 3, 1)
    plan = plan_from_deadline(
        start_date=start,
        deadline=deadline,
        committed_topics=set(),
        role_topics=["LLM"],
    )
    assert plan["feasible"] is False
    assert plan["days"] == []


def test_today_plan_tasks_filters_by_date():
    plan = {
        "days": [
            {"date": "2026-04-01", "topic": "LLM"},
            {"date": "2026-04-02", "topic": "RAG"},
        ]
    }
    tasks = today_plan_tasks(plan, on_date=date(2026, 4, 2))
    assert len(tasks) == 1
    assert tasks[0]["topic"] == "RAG"


def test_pack_density_increases_when_days_shrink():
    from app.interview.learning_path import pack_density

    assert pack_density(6, 6) == 1
    assert pack_density(6, 3) == 2
    assert pack_density(6, 2) == 3


def test_compressed_plan_packs_multiple_units_per_day():
    start = date(2026, 7, 1)
    # Very short window → must pack denser than 1 unit/day for s1 alone if only LLM incomplete
    deadline = start + timedelta(days=2)  # 3 days total
    plan = plan_from_deadline(
        start_date=start,
        deadline=deadline,
        committed_topics=set(),
        role_topics=["LLM"],
    )
    train_days = [d for d in plan["days"] if d["task_type"] == "train"]
    assert train_days
    assert max(int(d.get("units_packed") or 1) for d in train_days) >= 2
    assert plan.get("max_units_per_day", 1) >= 2


def test_active_day_blocks_until_completed():
    from app.interview.learning_path import resolve_active_learning_day

    plan = {
        "days": [
            {
                "date": "2026-07-20",
                "topic": "LLM",
                "learning_status": "pending",
                "section_title": "Transformer",
            },
            {
                "date": "2026-07-21",
                "topic": "LLM",
                "learning_status": "pending",
                "section_title": "Token",
            },
        ]
    }
    active = resolve_active_learning_day(plan, on_date=date(2026, 7, 21))
    assert active is not None
    assert active["date"] == "2026-07-20"

    plan["days"][0]["learning_status"] = "completed"
    active2 = resolve_active_learning_day(plan, on_date=date(2026, 7, 21))
    assert active2 is not None
    assert active2["date"] == "2026-07-21"


def test_list_learning_docs_history_order_and_cache():
    from types import SimpleNamespace

    from app.interview.plan_service import list_learning_docs

    profile = SimpleNamespace(
        learning_plan={
            "start_date": "2026-07-20",
            "days": [
                {
                    "date": "2026-07-20",
                    "topic": "LLM",
                    "title": "大模型",
                    "task_type": "train",
                    "section_title": "Transformer",
                    "learning_status": "pending",
                    "generated_doc": {
                        "doc_title": "大模型",
                        "section_title": "Transformer",
                        "topic": "LLM",
                        "reading_bullets": ["a"],
                        "comic_url": None,
                        "bank_excerpts": [],
                        "markdown_body": "## 知识讲解\n\nx\n\n## 面试题与详解\n\n**答案**\ny",
                        "generated_by": "llm",
                        "format_version": "qa_v1",
                    },
                },
                {
                    "date": "2026-07-21",
                    "topic": "LLM",
                    "title": "大模型",
                    "task_type": "train",
                    "section_title": "Token",
                    "learning_status": "pending",
                },
                {
                    "date": "2099-01-01",
                    "topic": "RAG",
                    "title": "未来",
                    "task_type": "train",
                },
            ],
        }
    )
    hist = list_learning_docs(profile)
    assert hist.has_plan is True
    # Only days with a usable generated handout — bare calendar slots omitted
    assert [i.date for i in hist.items] == ["2026-07-20"]
    assert hist.items[0].has_doc is True
    assert hist.items[0].generated_by == "llm"


def test_list_learning_docs_skips_backlog_calendar_without_doc():
    """While stuck on an older day, today's plan row without a doc must not list."""
    from types import SimpleNamespace
    from unittest.mock import patch

    from app.interview.plan_service import list_learning_docs

    profile = SimpleNamespace(
        learning_plan={
            "start_date": "2026-07-22",
            "days": [
                {
                    "date": "2026-07-22",
                    "topic": "LLM",
                    "title": "大模型",
                    "section_title": "Transformer 与注意力机制",
                    "task_type": "train",
                    "learning_status": "pending",
                    "generated_doc": {
                        "doc_title": "大模型",
                        "section_title": "Transformer 与注意力机制",
                        "topic": "LLM",
                        "reading_bullets": ["a"],
                        "comic_url": None,
                        "bank_excerpts": [],
                        "markdown_body": "## 知识讲解\n\nx\n\n## 面试题与详解\n\n**答案**\ny",
                        "generated_by": "llm",
                        "format_version": "qa_v1",
                    },
                },
                {
                    "date": "2026-07-23",
                    "topic": "LLM",
                    "title": "大模型",
                    "section_title": "Token、上下文窗口与成本",
                    "task_type": "train",
                    "learning_status": "pending",
                },
            ],
        }
    )
    with patch("app.interview.plan_service.date") as mock_date:
        mock_date.today.return_value = date(2026, 7, 23)
        mock_date.fromisoformat = date.fromisoformat
        hist = list_learning_docs(profile)
    assert [i.date for i in hist.items] == ["2026-07-22"]
    assert hist.items[0].is_active is True
    assert hist.items[0].is_today is False

def test_incomplete_days_before_excludes_today():
    """Yesterday unfinished should count as 1 backlog day, not include today's pending day."""
    from app.interview.learning_path import incomplete_days_before

    plan = {
        "days": [
            {"date": "2026-07-21", "learning_status": "completed", "topic": "LLM"},
            {"date": "2026-07-22", "learning_status": "pending", "topic": "LLM"},
            {"date": "2026-07-23", "learning_status": "pending", "topic": "LLM"},
        ]
    }
    backlog = incomplete_days_before(plan, on_date=date(2026, 7, 23))
    assert [d["date"] for d in backlog] == ["2026-07-22"]


def test_incomplete_days_before_counts_multiple_past_days():
    from app.interview.learning_path import incomplete_days_before

    plan = {
        "days": [
            {"date": "2026-07-21", "learning_status": "pending", "topic": "LLM"},
            {"date": "2026-07-22", "learning_status": "pending", "topic": "LLM"},
            {"date": "2026-07-23", "learning_status": "pending", "topic": "LLM"},
        ]
    }
    backlog = incomplete_days_before(plan, on_date=date(2026, 7, 23))
    assert [d["date"] for d in backlog] == ["2026-07-21", "2026-07-22"]

