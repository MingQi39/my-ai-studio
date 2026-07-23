"""Learning plan generation and push helpers for Interview Navigator."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.interview.daily_doc_generator import (
    doc_from_cache,
    doc_to_cache,
    generate_daily_learning_doc,
    is_usable_learning_doc,
    push_message_for_doc,
)
from app.interview.learning_curriculum import format_learning_doc_message, reading_unit_for_day
from app.interview.learning_path import (
    incomplete_days_before,
    rebalance_plan_preserving_completed,
    resolve_active_learning_day,
    today_plan_tasks,
)
from app.interview.schemas import (
    LearningDayStatusResponse,
    LearningDocByDateResponse,
    LearningDocHistoryItem,
    LearningDocHistoryResponse,
    LearningPlanResponse,
    PlanDayTask,
    PushSettingsResponse,
    PushSettingsUpdate,
    TodayLearningDoc,
    TodayPlanResponse,
)
from app.interview.training import topics_for_role
from app.models.database import (
    InterviewProfile,
    InterviewQuestionItem,
    InterviewReviewCard,
    InterviewTrainingAttempt,
)

PUSH_FREQUENCIES = frozenset({"daily", "weekdays", "weekends"})
DEFAULT_PUSH_FREQUENCY = "weekdays"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _committed_topics(attempts: list[InterviewTrainingAttempt]) -> set[str]:
    return {str(a.topic) for a in attempts if a.topic}


async def _load_plan_context(db: AsyncSession, profile: InterviewProfile) -> tuple[set[str], list[str]]:
    attempts = list(
        (
            await db.execute(
                select(InterviewTrainingAttempt).where(
                    InterviewTrainingAttempt.profile_id == profile.id,
                    InterviewTrainingAttempt.status == "committed",
                )
            )
        ).scalars()
    )
    role_topics = list(topics_for_role(profile.target_role))
    return _committed_topics(attempts), role_topics


def _plan_response(profile: InterviewProfile, plan: dict[str, Any]) -> LearningPlanResponse:
    deadline = profile.target_deadline
    days_remaining = None
    if deadline:
        days_remaining = max(0, (deadline - date.today()).days)
    return LearningPlanResponse(
        deadline=plan.get("deadline"),
        start_date=plan.get("start_date"),
        total_days=int(plan.get("total_days") or 0),
        days=[PlanDayTask.model_validate(day) for day in plan.get("days", [])],
        summary=str(plan.get("summary") or ""),
        feasible=bool(plan.get("feasible", True)),
        default_span_days=plan.get("default_span_days"),
        plan_generated_at=profile.plan_generated_at,
        days_remaining=days_remaining,
        max_units_per_day=plan.get("max_units_per_day"),
    )


async def generate_learning_plan(db: AsyncSession, profile: InterviewProfile) -> LearningPlanResponse:
    if profile.target_deadline is None:
        return LearningPlanResponse(summary="请先设置目标达成时间")
    committed, role_topics = await _load_plan_context(db, profile)
    plan = rebalance_plan_preserving_completed(
        existing=profile.learning_plan or {},
        start_date=date.today(),
        deadline=profile.target_deadline,
        committed_topics=committed,
        role_topics=role_topics,
    )
    profile.learning_plan = plan
    profile.plan_generated_at = _utcnow()
    await db.commit()
    await db.refresh(profile)
    return _plan_response(profile, plan)


async def get_learning_plan(db: AsyncSession, profile: InterviewProfile) -> LearningPlanResponse:
    plan = profile.learning_plan or {}
    if not plan and profile.target_deadline:
        return await generate_learning_plan(db, profile)
    return _plan_response(profile, plan)


async def _bank_excerpts_for_topic(
    db: AsyncSession, topic: str, *, limit: int = 3, offset: int = 0
) -> list[str]:
    """Pull interview-guide stems as today's document excerpts (no LLM)."""
    result = await db.execute(
        select(InterviewQuestionItem.normalized_question)
        .where(
            InterviewQuestionItem.is_active.is_(True),
            InterviewQuestionItem.topic == topic,
        )
        .order_by(InterviewQuestionItem.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    return [row[0] for row in result.all() if row[0]]


def _enrich_task_if_needed(task: PlanDayTask, day_index: int = 0) -> PlanDayTask:
    if task.reading_bullets and task.doc_title:
        return task
    doc_title, section_title, bullets = reading_unit_for_day(
        task.stage_id, task_type=task.task_type, day_index_in_stage=day_index
    )
    return task.model_copy(
        update={
            "doc_title": doc_title,
            "section_title": section_title,
            "reading_bullets": list(bullets),
            "message": format_learning_doc_message(doc_title, section_title, bullets),
        }
    )


def _learning_doc_from_task(task: PlanDayTask, bank_excerpts: list[str]) -> TodayLearningDoc:
    return TodayLearningDoc(
        doc_title=task.doc_title or task.title,
        section_title=task.section_title or "今日阅读",
        topic=task.topic,
        reading_bullets=task.reading_bullets,
        comic_url=task.comic_url,
        bank_excerpts=bank_excerpts,
    )


def _cached_doc_for_date(plan: dict[str, Any], iso_date: str) -> TodayLearningDoc | None:
    for day in plan.get("days", []):
        if day.get("date") == iso_date and day.get("generated_doc"):
            try:
                doc = doc_from_cache(day["generated_doc"])
            except Exception:
                return None
            if is_usable_learning_doc(doc):
                return doc
            return None
    return None


async def _persist_generated_doc(
    db: AsyncSession, profile: InterviewProfile, iso_date: str, doc: TodayLearningDoc
) -> None:
    plan = dict(profile.learning_plan or {})
    days: list[dict[str, Any]] = []
    for day in plan.get("days", []):
        row = dict(day)
        if row.get("date") == iso_date:
            row["generated_doc"] = doc_to_cache(doc)
        days.append(row)
    plan["days"] = days
    profile.learning_plan = plan
    await db.commit()
    await db.refresh(profile)


async def get_today_plan(
    db: AsyncSession, profile: InterviewProfile, *, force_refresh: bool = False
) -> TodayPlanResponse:
    today = date.today()
    today_iso = today.isoformat()
    plan = profile.learning_plan or {}
    # If deadline moved earlier vs stored plan, rebalance density automatically.
    if profile.target_deadline and plan.get("deadline"):
        try:
            stored_deadline = date.fromisoformat(str(plan["deadline"]))
            if profile.target_deadline < stored_deadline:
                await generate_learning_plan(db, profile)
                plan = profile.learning_plan or {}
        except ValueError:
            pass

    active_raw = resolve_active_learning_day(plan, on_date=today)
    incomplete = incomplete_days_before(plan, on_date=today)
    is_backlog = bool(active_raw and str(active_raw.get("date")) < today_iso)
    active_iso = str(active_raw.get("date")) if active_raw else today_iso

    calendar_tasks = [PlanDayTask.model_validate(t) for t in today_plan_tasks(plan, on_date=today)]
    if active_raw:
        active_task = _enrich_task_if_needed(
            PlanDayTask.model_validate(active_raw),
            day_index=_day_index_for_date(plan, active_iso),
        )
        # Surface the active (possibly backlog) day as the primary task.
        tasks = [active_task]
        for t in calendar_tasks:
            if t.date != active_task.date:
                tasks.append(t)
    else:
        tasks = calendar_tasks

    due_count = len(
        list(
            (
                await db.execute(
                    select(InterviewReviewCard).where(
                        InterviewReviewCard.profile_id == profile.id,
                        InterviewReviewCard.next_due_at.is_not(None),
                        InterviewReviewCard.next_due_at <= _utcnow(),
                        InterviewReviewCard.status.in_(["new", "learning", "reviewing"]),
                    )
                )
            ).scalars()
        )
    )
    push_message = None
    learning_doc: TodayLearningDoc | None = None
    tz_name = profile.push_timezone or "Asia/Shanghai"
    local_today = _local_now(tz_name).date()
    push_due_today = should_push_on_date(profile.push_frequency or DEFAULT_PUSH_FREQUENCY, local_today)
    learning_status = None
    units_packed = 1

    primary = tasks[0] if tasks else None
    if primary:
        learning_status = primary.learning_status
        units_packed = max(1, primary.units_packed or 1)
        day_offset = _day_index_for_date(plan, primary.date)
        learning_doc = None if force_refresh else _cached_doc_for_date(plan, primary.date)
        if learning_doc is None:
            learning_doc = await generate_daily_learning_doc(
                db,
                profile=profile,
                task=primary,
                day_offset=day_offset,
            )
            await _persist_generated_doc(db, profile, primary.date, learning_doc)
            plan = profile.learning_plan or {}

        if is_backlog or (learning_status != "completed" and primary.date < today_iso):
            section = primary.section_title or primary.title
            push_message = (
                f"你还有未完成的学习（{primary.date} · {section}）。"
                f"请先完成后再解锁新内容；当前积压 {len(incomplete)} 天。"
            )
        elif learning_status == "completed" and primary.date == today_iso:
            push_message = f"今日学习已完成：{primary.section_title or primary.title}。明天继续推送新内容。"
        else:
            push_message = push_message_for_doc(learning_doc)
            if units_packed > 1:
                push_message = f"【加密日 · {units_packed} 节】\n{push_message}"
    elif push_due_today and due_count:
        push_message = f"今日有 {due_count} 张复习卡到期，建议先口述复习"

    return TodayPlanResponse(
        date=today.isoformat(),
        tasks=tasks,
        due_review_count=due_count,
        push_message=push_message,
        has_plan=bool(plan.get("days")),
        push_due_today=push_due_today,
        learning_doc=learning_doc,
        active_date=active_iso if primary else None,
        learning_status=learning_status,
        is_backlog=is_backlog,
        incomplete_count=len(incomplete),
        units_packed=units_packed,
    )


def _day_index_for_date(plan: dict[str, Any], iso_date: str) -> int:
    start = plan.get("start_date")
    if not start:
        return 0
    try:
        return max(0, (date.fromisoformat(iso_date) - date.fromisoformat(str(start))).days)
    except ValueError:
        return 0


def _raw_day_for_date(plan: dict[str, Any], iso_date: str) -> dict[str, Any] | None:
    for day in plan.get("days", []):
        if day.get("date") == iso_date:
            return day
    return None


def list_learning_docs(profile: InterviewProfile) -> LearningDocHistoryResponse:
    """List generated learning docs only (not bare calendar days).

    Plan days without a usable ``generated_doc`` are omitted — e.g. while the
    user is still on a backlog day, "today" must not appear as an empty slot.
    """
    plan = profile.learning_plan or {}
    days = list(plan.get("days") or [])
    if not days:
        return LearningDocHistoryResponse(items=[], has_plan=False)

    today_iso = date.today().isoformat()
    active = resolve_active_learning_day(plan, on_date=date.today())
    active_date = str(active.get("date")) if active else None
    items: list[LearningDocHistoryItem] = []
    for raw in days:
        iso = str(raw.get("date") or "")
        if not iso or iso > today_iso:
            continue
        cached = None
        generated_by = None
        if raw.get("generated_doc"):
            try:
                cached = doc_from_cache(raw["generated_doc"])
            except Exception:
                cached = None
            if cached and is_usable_learning_doc(cached):
                generated_by = cached.generated_by
            else:
                cached = None
        if cached is None:
            continue
        status = raw.get("learning_status") or "pending"
        if status not in {"pending", "completed"}:
            status = "pending"
        items.append(
            LearningDocHistoryItem(
                date=iso,
                topic=str(raw.get("topic") or ""),
                title=str(raw.get("title") or raw.get("doc_title") or raw.get("topic") or "学习日"),
                section_title=(
                    cached.section_title
                    or raw.get("section_title")
                    or raw.get("doc_title")
                ),
                task_type=raw.get("task_type") or "train",  # type: ignore[arg-type]
                has_doc=True,
                generated_by=generated_by,
                is_today=iso == today_iso,
                learning_status=status,  # type: ignore[arg-type]
                is_active=iso == active_date,
                units_packed=int(raw.get("units_packed") or 1),
            )
        )
    items.sort(key=lambda x: x.date, reverse=True)
    return LearningDocHistoryResponse(items=items, has_plan=True)


async def set_learning_day_status(
    db: AsyncSession,
    profile: InterviewProfile,
    iso_date: str,
    *,
    status: str,
) -> LearningDayStatusResponse:
    try:
        date.fromisoformat(iso_date)
    except ValueError as exc:
        raise ValueError("日期格式应为 YYYY-MM-DD") from exc
    if status not in {"pending", "completed"}:
        raise ValueError("status 必须是 pending 或 completed")

    plan = dict(profile.learning_plan or {})
    found = False
    completed_at = None
    days: list[dict[str, Any]] = []
    for day in plan.get("days", []):
        row = dict(day)
        if row.get("date") == iso_date:
            found = True
            row["learning_status"] = status
            if status == "completed":
                completed_at = _utcnow().isoformat()
                row["completed_at"] = completed_at
            else:
                row["completed_at"] = None
                completed_at = None
        days.append(row)
    if not found:
        raise LookupError(f"计划中没有 {iso_date} 这一天")

    plan["days"] = days
    profile.learning_plan = plan
    await db.commit()
    await db.refresh(profile)

    today = date.today()
    active = resolve_active_learning_day(profile.learning_plan, on_date=today)
    incomplete = incomplete_days_before(profile.learning_plan, on_date=today)
    return LearningDayStatusResponse(
        date=iso_date,
        learning_status=status,  # type: ignore[arg-type]
        completed_at=completed_at,
        active_date=str(active.get("date")) if active else None,
        incomplete_count=len(incomplete),
    )


async def get_learning_doc_for_date(
    db: AsyncSession,
    profile: InterviewProfile,
    iso_date: str,
    *,
    force_refresh: bool = False,
) -> LearningDocByDateResponse:
    try:
        date.fromisoformat(iso_date)
    except ValueError as exc:
        raise ValueError("日期格式应为 YYYY-MM-DD") from exc

    plan = profile.learning_plan or {}
    raw = _raw_day_for_date(plan, iso_date)
    if raw is None:
        raise LookupError(f"计划中没有 {iso_date} 这一天")

    task = _enrich_task_if_needed(
        PlanDayTask.model_validate(raw),
        day_index=_day_index_for_date(plan, iso_date),
    )
    learning_doc = None if force_refresh else _cached_doc_for_date(plan, iso_date)
    if learning_doc is None:
        learning_doc = await generate_daily_learning_doc(
            db,
            profile=profile,
            task=task,
            day_offset=_day_index_for_date(plan, iso_date),
        )
        await _persist_generated_doc(db, profile, iso_date, learning_doc)

    return LearningDocByDateResponse(date=iso_date, learning_doc=learning_doc, task=task)


def push_settings_response(profile: InterviewProfile) -> PushSettingsResponse:
    frequency = profile.push_frequency or DEFAULT_PUSH_FREQUENCY
    if frequency not in PUSH_FREQUENCIES:
        frequency = DEFAULT_PUSH_FREQUENCY
    return PushSettingsResponse(
        push_enabled=bool(profile.push_enabled),
        push_time=profile.push_time or "21:00",
        push_timezone=profile.push_timezone or "Asia/Shanghai",
        push_frequency=frequency,  # type: ignore[arg-type]
        target_deadline=profile.target_deadline,
        last_push_date=profile.last_push_date,
    )


async def update_push_settings(
    db: AsyncSession, profile: InterviewProfile, data: PushSettingsUpdate
) -> PushSettingsResponse:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    if profile.push_enabled and not profile.push_time:
        profile.push_time = "21:00"
    if not profile.push_frequency or profile.push_frequency not in PUSH_FREQUENCIES:
        profile.push_frequency = DEFAULT_PUSH_FREQUENCY
    await db.commit()
    await db.refresh(profile)
    return push_settings_response(profile)


def _local_now(tz_name: str) -> datetime:
    try:
        return datetime.now(ZoneInfo(tz_name))
    except Exception:
        return datetime.now(ZoneInfo("Asia/Shanghai"))


def should_push_on_date(frequency: str, on_date: date) -> bool:
    """Return whether a push should fire on the given local calendar date."""
    weekday = on_date.weekday()  # Mon=0 .. Sun=6
    if frequency == "weekdays":
        return weekday < 5
    if frequency == "weekends":
        return weekday >= 5
    return True


def is_push_due(profile: InterviewProfile, *, now: datetime | None = None) -> bool:
    if not profile.push_enabled or not profile.target_deadline:
        return False
    tz_name = profile.push_timezone or "Asia/Shanghai"
    local = _local_now(tz_name) if now is None else now.astimezone(ZoneInfo(tz_name))
    frequency = profile.push_frequency or DEFAULT_PUSH_FREQUENCY
    if not should_push_on_date(frequency, local.date()):
        return False
    push_time = profile.push_time or "21:00"
    hour, minute = map(int, push_time.split(":"))
    if local.hour != hour or local.minute != minute:
        return False
    if profile.last_push_date == local.date():
        return False
    return True


async def mark_push_sent(db: AsyncSession, profile: InterviewProfile) -> None:
    tz_name = profile.push_timezone or "Asia/Shanghai"
    profile.last_push_date = _local_now(tz_name).date()
    await db.commit()


async def process_due_pushes(db: AsyncSession) -> int:
    """Mark profiles due for push; returns count processed. Frontend delivers browser notifications."""
    result = await db.execute(
        select(InterviewProfile).where(
            InterviewProfile.push_enabled.is_(True),
            InterviewProfile.target_deadline.is_not(None),
        )
    )
    profiles = list(result.scalars())
    sent = 0
    for profile in profiles:
        if not is_push_due(profile):
            continue
        await mark_push_sent(db, profile)
        sent += 1
    return sent
