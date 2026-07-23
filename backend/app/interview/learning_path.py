"""Map guide 6-stage learning path → existing interview topics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

from app.interview.learning_curriculum import (
    STAGE_READING_UNITS,
    format_learning_doc_message,
    reading_bundle_for_unit_indices,
    reading_unit_for_day,
    stage_unit_count,
)

PlanTaskType = Literal["train", "review", "consolidate"]
LearningDayStatus = Literal["pending", "completed"]


def _day_entry(
    *,
    day: date,
    task_type: PlanTaskType,
    stage_id: str | None,
    stage_title: str,
    topic: str,
    goal: str,
    day_index_in_stage: int,
    unit_indices: list[int] | None = None,
) -> dict[str, Any]:
    if unit_indices is not None and task_type == "train" and stage_id:
        doc_title, section_title, bullets, unit_keys = reading_bundle_for_unit_indices(
            stage_id, unit_indices, task_type=task_type
        )
    else:
        doc_title, section_title, bullets = reading_unit_for_day(
            stage_id,
            task_type=task_type,
            day_index_in_stage=day_index_in_stage,
            topic=topic,
        )
        unit_keys = (
            [f"{stage_id}:{day_index_in_stage % stage_unit_count(stage_id)}"]
            if stage_id and task_type == "train"
            else []
        )
    comic = comic_url_for_topic(topic)
    return {
        "date": day.isoformat(),
        "task_type": task_type,
        "stage_id": stage_id,
        "title": stage_title,
        "topic": topic,
        "goal": goal,
        "doc_title": doc_title,
        "section_title": section_title,
        "reading_bullets": list(bullets),
        "unit_keys": unit_keys,
        "units_packed": max(1, len(unit_keys)),
        "comic_url": comic,
        "message": format_learning_doc_message(doc_title, section_title, bullets),
        "learning_status": "pending",
        "completed_at": None,
    }


@dataclass(frozen=True)
class LearningStage:
    id: str
    title: str
    goal: str
    topics: tuple[str, ...]
    comic: str | None
    days_hint: str


# Aligned with ai-agent-interview-guide docs/00-学习路线图 (compressed onto our topics).
LEARNING_STAGES: tuple[LearningStage, ...] = (
    LearningStage(
        id="s1_llm_prompt",
        title="大模型与 Prompt",
        goal="Transformer / Token 直觉 + 结构化提示、Few-shot、CoT",
        topics=("LLM",),
        comic="01-什么是Agent.png",
        days_hint="约 60～80 天",
    ),
    LearningStage(
        id="s2_rag",
        title="RAG 技术",
        goal="分块、检索、重排与幻觉治理能串成一条链路",
        topics=("RAG",),
        comic="03-RAG流程.png",
        days_hint="约 30～40 天",
    ),
    LearningStage(
        id="s3_agent_tools",
        title="Agent 框架与工具",
        goal="ReAct / LangGraph / Tool calling / MCP 能讲清取舍",
        topics=("Agent", "LangGraph"),
        comic="02-ReAct循环.png",
        days_hint="约 35～45 天",
    ),
    LearningStage(
        id="s4_memory_multi",
        title="记忆与多智能体",
        goal="短长期记忆设计；多 Agent 协作可结合 Agent 主题巩固",
        topics=("Memory",),
        comic="05-记忆系统.png",
        days_hint="约 30～40 天",
    ),
    LearningStage(
        id="s5_engineering",
        title="工程化与项目表达",
        goal="可观测、熔断降级、成本；项目题能走到取舍与证据",
        topics=("可观测性", "Agent 评测"),
        comic="06-面试场景.png",
        days_hint="约 40～50 天",
    ),
)

STAGE_DEFAULT_DAYS: dict[str, int] = {
    "s1_llm_prompt": 70,
    "s2_rag": 35,
    "s3_agent_tools": 40,
    "s4_memory_multi": 35,
    "s5_engineering": 45,
}

TOPIC_COMIC: dict[str, str] = {
    "LLM": "01-什么是Agent.png",
    "Agent": "01-什么是Agent.png",
    "LangGraph": "02-ReAct循环.png",
    "RAG": "03-RAG流程.png",
    "Memory": "05-记忆系统.png",
    "可观测性": "06-面试场景.png",
    "Agent 评测": "04-多Agent协作.png",
}

COMIC_PUBLIC_PREFIX = "/interview/comics/"


def comic_url_for_topic(topic: str | None) -> str | None:
    if not topic:
        return None
    name = TOPIC_COMIC.get(topic) or TOPIC_COMIC.get(topic.strip())
    if not name:
        for key, filename in TOPIC_COMIC.items():
            if key.lower() in topic.lower() or topic.lower() in key.lower():
                name = filename
                break
    if not name:
        return None
    return f"{COMIC_PUBLIC_PREFIX}{name}"


def _stage_covered(stage: LearningStage, committed_topics: set[str]) -> bool:
    """A stage is covered when at least one of its topics has a committed attempt."""
    committed_l = {t.lower() for t in committed_topics}
    return any(t.lower() in committed_l for t in stage.topics)


def recommend_learning_path(
    *,
    committed_topics: set[str],
    role_topics: list[str] | None = None,
) -> dict[str, Any]:
    """
    Recommend the first incomplete stage as next_module.
    Stages whose topics are entirely outside the role bank stay listed but
    are skipped for "next" when role_topics is provided.
    """
    role_set = {t.lower() for t in (role_topics or [])} if role_topics else None
    stages_out: list[dict[str, Any]] = []
    next_module: dict[str, Any] | None = None

    for stage in LEARNING_STAGES:
        done = _stage_covered(stage, committed_topics)
        relevant = True
        if role_set is not None:
            relevant = any(t.lower() in role_set for t in stage.topics) or not role_set
        primary_topic = stage.topics[0]
        for t in stage.topics:
            if role_set is None or t.lower() in role_set:
                primary_topic = t
                break
        row = {
            "id": stage.id,
            "title": stage.title,
            "goal": stage.goal,
            "topics": list(stage.topics),
            "primary_topic": primary_topic,
            "comic_url": f"{COMIC_PUBLIC_PREFIX}{stage.comic}" if stage.comic else None,
            "days_hint": stage.days_hint,
            "done": done,
            "relevant": relevant,
        }
        stages_out.append(row)
        if next_module is None and relevant and not done:
            next_module = {
                "stage_id": stage.id,
                "title": stage.title,
                "topic": primary_topic,
                "goal": stage.goal,
                "comic_url": row["comic_url"],
                "reason": f"阶段「{stage.title}」尚未完成闭环，建议先练「{primary_topic}」",
            }

    if next_module is None:
        next_module = {
            "stage_id": None,
            "title": "巩固与拓宽",
            "topic": (role_topics[0] if role_topics else "Agent"),
            "goal": "路线阶段已基本覆盖，可复习卡或换项目模拟加深证据",
            "comic_url": f"{COMIC_PUBLIC_PREFIX}06-面试场景.png",
            "reason": "学习路线相关主题均已有闭环，保持复习或开「项目模拟」",
        }

    done_count = sum(1 for s in stages_out if s["done"] and s["relevant"])
    relevant_count = sum(1 for s in stages_out if s["relevant"]) or 1
    return {
        "stages": stages_out,
        "next_module": next_module,
        "done_count": done_count,
        "total_relevant": relevant_count,
    }


def _primary_topic(stage: LearningStage, role_set: set[str] | None) -> str:
    for topic in stage.topics:
        if role_set is None or topic.lower() in role_set:
            return topic
    return stage.topics[0]


def _allocate_stage_days(incomplete: list[LearningStage], total_days: int) -> list[tuple[LearningStage, int]]:
    """Distribute calendar days across incomplete stages proportionally."""
    if total_days <= 0 or not incomplete:
        return []
    if len(incomplete) == 1:
        return [(incomplete[0], total_days)]
    weights = [STAGE_DEFAULT_DAYS.get(stage.id, 30) for stage in incomplete]
    weight_sum = sum(weights) or 1
    raw = [max(1, round(total_days * w / weight_sum)) for w in weights]
    diff = total_days - sum(raw)
    idx = 0
    while diff != 0 and raw:
        if diff > 0:
            raw[idx % len(raw)] += 1
            diff -= 1
        else:
            if raw[idx % len(raw)] > 1:
                raw[idx % len(raw)] -= 1
                diff += 1
        idx += 1
    return list(zip(incomplete, raw, strict=True))


def pack_density(unit_count: int, span_days: int) -> int:
    """How many curriculum units to merge into one calendar day."""
    if span_days <= 0:
        return max(1, unit_count)
    return max(1, math.ceil(unit_count / span_days))


def _pack_stage_days(
    *,
    stage: LearningStage,
    span: int,
    start_date: date,
    day_offset: int,
    total_days: int,
    role_set: set[str] | None,
) -> list[dict[str, Any]]:
    """Emit `span` calendar days for a stage, packing denser when span is short."""
    topic = _primary_topic(stage, role_set)
    units = STAGE_READING_UNITS.get(stage.id, ())
    n_units = len(units) or 1
    density = pack_density(n_units, span)
    out: list[dict[str, Any]] = []
    cursor = 0
    for i in range(span):
        if day_offset + i >= total_days:
            break
        day = start_date + timedelta(days=day_offset + i)
        if cursor < n_units:
            indices = list(range(cursor, min(cursor + density, n_units)))
            cursor += density
            task_type: PlanTaskType = "train"
            day_index = indices[0]
            unit_indices = indices
        else:
            # Extra calendar days after content is covered → review / consolidate rhythm.
            task_type = "review" if i % 2 == 0 else "consolidate"
            day_index = i
            unit_indices = None
        out.append(
            _day_entry(
                day=day,
                task_type=task_type,
                stage_id=stage.id,
                stage_title=stage.title,
                topic=topic,
                goal=stage.goal,
                day_index_in_stage=day_index,
                unit_indices=unit_indices,
            )
        )
    return out


def plan_from_deadline(
    *,
    start_date: date,
    deadline: date,
    committed_topics: set[str],
    role_topics: list[str] | None = None,
) -> dict[str, Any]:
    """
    Build a day-by-day learning plan from today until the goal deadline.
    Incomplete stages are compressed or stretched relative to STAGE_DEFAULT_DAYS.
    When calendar days are fewer than curriculum units, multiple units pack into one day.
    """
    if deadline < start_date:
        return {
            "deadline": deadline.isoformat(),
            "start_date": start_date.isoformat(),
            "total_days": 0,
            "days": [],
            "summary": "目标日期已过，请更新达成时间后重新生成计划。",
            "feasible": False,
        }

    role_set = {t.lower() for t in (role_topics or [])} if role_topics else None
    total_days = (deadline - start_date).days + 1
    relevant_stages: list[LearningStage] = []
    incomplete: list[LearningStage] = []
    for stage in LEARNING_STAGES:
        relevant = True
        if role_set is not None:
            relevant = any(t.lower() in role_set for t in stage.topics) or not role_set
        if not relevant:
            continue
        relevant_stages.append(stage)
        if not _stage_covered(stage, committed_topics):
            incomplete.append(stage)

    days_out: list[dict[str, Any]] = []

    # Role bank has no overlap with AI curriculum stages (e.g. 前端/全栈) —
    # schedule role topics as train days, do NOT fake "巩固拓宽" with React.
    if not relevant_stages:
        bank = list(role_topics) if role_topics else ["Agent"]
        for offset in range(total_days):
            day = start_date + timedelta(days=offset)
            topic = bank[offset % len(bank)]
            days_out.append(
                _day_entry(
                    day=day,
                    task_type="train",
                    stage_id=None,
                    stage_title=f"{topic} 专题",
                    topic=topic,
                    goal=f"围绕 {topic} 建立可面试表达的闭环",
                    day_index_in_stage=offset,
                )
            )
        return {
            "deadline": deadline.isoformat(),
            "start_date": start_date.isoformat(),
            "total_days": total_days,
            "days": days_out,
            "summary": f"共 {total_days} 天，按岗位主题轮转训练（当前路线阶段与岗位题库无交集）",
            "feasible": True,
            "max_units_per_day": 1,
        }

    if not incomplete:
        bank = list(role_topics) if role_topics else ["Agent"]
        for offset in range(total_days):
            day = start_date + timedelta(days=offset)
            topic = bank[offset % len(bank)]
            days_out.append(
                _day_entry(
                    day=day,
                    task_type="consolidate",
                    stage_id=None,
                    stage_title="巩固与拓宽",
                    topic=topic,
                    goal="路线阶段已基本覆盖，保持复习或项目模拟",
                    day_index_in_stage=offset,
                )
            )
        return {
            "deadline": deadline.isoformat(),
            "start_date": start_date.isoformat(),
            "total_days": total_days,
            "days": days_out,
            "summary": f"共 {total_days} 天巩固期，重点复习与项目表达",
            "feasible": True,
            "max_units_per_day": 1,
        }

    allocations = _allocate_stage_days(incomplete, total_days)
    default_span = sum(STAGE_DEFAULT_DAYS.get(s.id, 30) for s in incomplete)
    feasible = total_days >= len(incomplete)
    day_offset = 0
    max_units = 1

    for stage, span in allocations:
        packed = _pack_stage_days(
            stage=stage,
            span=span,
            start_date=start_date,
            day_offset=day_offset,
            total_days=total_days,
            role_set=role_set,
        )
        for row in packed:
            max_units = max(max_units, int(row.get("units_packed") or 1))
        days_out.extend(packed)
        day_offset += len(packed)

    last = incomplete[-1]
    last_topic = _primary_topic(last, role_set)
    consolidate_idx = 0
    while day_offset < total_days:
        day = start_date + timedelta(days=day_offset)
        days_out.append(
            _day_entry(
                day=day,
                task_type="consolidate",
                stage_id=last.id,
                stage_title=last.title,
                topic=last_topic,
                goal=last.goal,
                day_index_in_stage=consolidate_idx,
            )
        )
        consolidate_idx += 1
        day_offset += 1

    summary = f"共 {total_days} 天，覆盖 {len(incomplete)} 个未完成阶段"
    if total_days < default_span:
        summary += (
            f"（默认约需 {default_span} 天；已压缩，单日最多合并 {max_units} 个知识点包）"
        )
    return {
        "deadline": deadline.isoformat(),
        "start_date": start_date.isoformat(),
        "total_days": total_days,
        "days": days_out,
        "summary": summary,
        "feasible": feasible,
        "default_span_days": default_span,
        "max_units_per_day": max_units,
    }


def today_plan_tasks(plan: dict[str, Any] | None, *, on_date: date) -> list[dict[str, Any]]:
    if not plan:
        return []
    iso = on_date.isoformat()
    return [day for day in plan.get("days", []) if day.get("date") == iso]


def resolve_active_learning_day(
    plan: dict[str, Any] | None, *, on_date: date
) -> dict[str, Any] | None:
    """
    Earliest plan day on/before on_date that is not completed.
    Gate: unfinished days block advancing to newer content.
    """
    if not plan:
        return None
    today_iso = on_date.isoformat()
    candidates = [
        day
        for day in plan.get("days", [])
        if isinstance(day, dict) and day.get("date") and str(day["date"]) <= today_iso
    ]
    candidates.sort(key=lambda d: str(d.get("date")))
    for day in candidates:
        if day.get("learning_status") != "completed":
            return day
    for day in reversed(candidates):
        if str(day.get("date")) == today_iso:
            return day
    return candidates[-1] if candidates else None


def incomplete_days_before(
    plan: dict[str, Any] | None, *, on_date: date
) -> list[dict[str, Any]]:
    """Incomplete plan days strictly before on_date (backlog only; excludes today)."""
    if not plan:
        return []
    today_iso = on_date.isoformat()
    out = [
        day
        for day in plan.get("days", [])
        if isinstance(day, dict)
        and day.get("date")
        and str(day["date"]) < today_iso
        and day.get("learning_status") != "completed"
    ]
    out.sort(key=lambda d: str(d.get("date")))
    return out


def rebalance_plan_preserving_completed(
    *,
    existing: dict[str, Any] | None,
    start_date: date,
    deadline: date,
    committed_topics: set[str],
    role_topics: list[str] | None = None,
) -> dict[str, Any]:
    """
    Keep completed days; rebuild the rest from start_date→deadline with packing density
    based on remaining curriculum vs remaining calendar days.
    """
    existing = existing or {}
    completed = [
        dict(day)
        for day in existing.get("days", [])
        if isinstance(day, dict) and day.get("learning_status") == "completed"
    ]
    completed.sort(key=lambda d: str(d.get("date")))

    fresh = plan_from_deadline(
        start_date=start_date,
        deadline=deadline,
        committed_topics=committed_topics,
        role_topics=role_topics,
    )
    if not completed:
        return fresh

    completed_dates = {str(d.get("date")) for d in completed}
    future = [dict(d) for d in fresh.get("days", []) if str(d.get("date")) not in completed_dates]
    merged = completed + future
    merged.sort(key=lambda d: str(d.get("date")))
    fresh["days"] = merged
    fresh["total_days"] = len(merged)
    fresh["preserved_completed"] = len(completed)
    max_units = max((int(d.get("units_packed") or 1) for d in future), default=1)
    fresh["max_units_per_day"] = max_units
    summary = str(fresh.get("summary") or "")
    if max_units > 1:
        summary += f"；未完成日程已按剩余天数加密（约 {max_units} 节/天）"
    if completed:
        summary += f"；已保留 {len(completed)} 个已完成学习日"
    fresh["summary"] = summary
    return fresh
