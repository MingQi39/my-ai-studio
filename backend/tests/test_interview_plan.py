"""Tests for deadline-based learning plan generation."""

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.interview.learning_path import plan_from_deadline, today_plan_tasks
from app.interview.training import topics_for_role


def test_ai_role_plan_never_includes_react():
    start = date(2026, 7, 23)
    plan = plan_from_deadline(
        start_date=start,
        deadline=start + timedelta(days=30),
        committed_topics=set(),
        role_topics=list(topics_for_role("AI 应用工程")),
    )
    topics = {day["topic"] for day in plan["days"]}
    assert "React" not in topics
    assert "LLM" in topics


def test_frontend_role_without_ai_stages_schedules_role_topics_as_train():
    """前端 topic bank 与 AI 路线阶段无交集时，不应假装「巩固拓宽」且整天 React。"""
    start = date(2026, 7, 23)
    plan = plan_from_deadline(
        start_date=start,
        deadline=start + timedelta(days=2),
        committed_topics=set(),
        role_topics=list(topics_for_role("前端")),
    )
    assert plan["days"]
    assert all(d["task_type"] == "train" for d in plan["days"])
    assert {d["topic"] for d in plan["days"]} <= set(topics_for_role("前端"))
    assert all(d["section_title"] != "巩固拓宽" for d in plan["days"])


def test_stale_frontend_plan_mismatches_ai_role():
    from app.interview.plan_service import plan_mismatches_role

    stale = {
        "days": [
            {
                "date": "2026-07-23",
                "topic": "React",
                "task_type": "consolidate",
                "title": "巩固与拓宽",
                "section_title": "巩固拓宽",
                "doc_title": "综合巩固",
            }
        ]
    }
    assert plan_mismatches_role(stale, list(topics_for_role("AI 应用工程"))) is True
    assert plan_mismatches_role(stale, list(topics_for_role("前端"))) is False


@pytest.mark.asyncio
async def test_update_profile_role_change_rebuilds_plan():
    from app.interview.schemas import InterviewProfileUpdate
    from app.interview.services import InterviewService

    profile = SimpleNamespace(
        target_role="前端",
        target_level="中级",
        target_deadline=date(2027, 4, 22),
        learning_plan={
            "days": [
                {
                    "date": "2026-07-23",
                    "topic": "React",
                    "task_type": "consolidate",
                    "section_title": "巩固拓宽",
                    "doc_title": "综合巩固",
                }
            ]
        },
        keywords=[],
    )
    db = AsyncMock()
    svc = InterviewService(db)
    with (
        patch.object(svc, "get_or_create_profile", AsyncMock(return_value=profile)),
        patch("app.interview.services.generate_learning_plan", AsyncMock()) as gen,
    ):
        await svc.update_profile(
            "00000000-0000-0000-0000-000000000001",
            InterviewProfileUpdate(target_role="AI 应用工程"),
        )
    assert profile.target_role == "AI 应用工程"
    assert profile.learning_plan in (None, {})
    gen.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_today_plan_heals_react_plan_under_ai_role():
    from app.interview.plan_service import get_today_plan

    profile = SimpleNamespace(
        id="p1",
        target_role="AI 应用工程",
        target_level="中级",
        target_deadline=date(2027, 4, 22),
        push_timezone="Asia/Shanghai",
        push_frequency="weekdays",
        learning_plan={
            "deadline": "2027-04-22",
            "start_date": "2026-07-23",
            "target_role": "前端",
            "days": [
                {
                    "date": "2026-07-23",
                    "topic": "React",
                    "task_type": "consolidate",
                    "title": "巩固与拓宽",
                    "section_title": "巩固拓宽",
                    "doc_title": "综合巩固",
                    "goal": "x",
                    "reading_bullets": ["a", "b", "c"],
                    "learning_status": "pending",
                }
            ],
        },
    )
    healed = {
        "deadline": "2027-04-22",
        "start_date": "2026-07-23",
        "target_role": "AI 应用工程",
        "days": [
                {
                    "date": "2026-07-23",
                    "topic": "LLM",
                    "task_type": "train",
                    "title": "大模型与 Prompt",
                    "section_title": "Transformer 与注意力机制",
                    "doc_title": "大模型与 Prompt 工程",
                    "goal": "Transformer",
                    "message": "LLM",
                    "reading_bullets": ["自注意力"],
                    "learning_status": "pending",
                }
        ],
    }

    async def _fake_generate(db, profile):
        profile.learning_plan = healed
        return SimpleNamespace(summary="healed")

    db = AsyncMock()
    execute_result = SimpleNamespace(scalars=lambda: SimpleNamespace(__iter__=lambda self: iter([])))
    # Also support list(scalars()) used by due review query
    class _Scalars:
        def all(self):
            return []

        def __iter__(self):
            return iter([])

    db.execute = AsyncMock(return_value=SimpleNamespace(scalars=lambda: _Scalars()))
    with (
        patch("app.interview.plan_service._load_plan_context", AsyncMock(return_value=(set(), list(topics_for_role("AI 应用工程"))))),
        patch("app.interview.plan_service.generate_learning_plan", side_effect=_fake_generate) as gen,
        patch("app.interview.plan_service.generate_daily_learning_doc", AsyncMock()) as gen_doc,
        patch("app.interview.plan_service._persist_generated_doc", AsyncMock()),
        patch("app.interview.plan_service.date") as mock_date,
    ):
        mock_date.today.return_value = date(2026, 7, 23)
        mock_date.fromisoformat = date.fromisoformat
        from app.interview.schemas import TodayLearningDoc

        gen_doc.return_value = TodayLearningDoc(
            doc_title="大模型与 Prompt 工程",
            section_title="Transformer 与注意力机制",
            topic="LLM",
            reading_bullets=["自注意力"],
            markdown_body="## 知识讲解\n今日主题 **LLM**\n\n## 面试题与详解\n**答案**\nx",
            generated_by="template",
            format_version="qa_v1",
        )
        resp = await get_today_plan(db, profile)

    gen.assert_awaited_once()
    assert resp.tasks
    assert resp.tasks[0].topic == "LLM"
    assert resp.learning_doc is not None
    assert resp.learning_doc.topic == "LLM"
    assert "React" not in (resp.learning_doc.markdown_body or "")


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

