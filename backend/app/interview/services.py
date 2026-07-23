"""Persistence boundary for Interview Navigator training attempts."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.interview.attempt_fsm import (
    ACTIVE_STATUSES,
    RULE_VERSION,
    active_attempt_matches_goal,
    after_answer_status,
    can_abandon,
    can_commit,
    can_submit_version,
)
from app.interview.schemas import (
    AbandonAttemptRequest,
    AnswerVersionPayload,
    AttemptHintRequest,
    CreateAttemptRequest,
    EvaluateAnswerRequest,
    EvaluateAnswerResponse,
    EvaluationTrace,
    HintPayload,
    HintRequest,
    HintResponse,
    InterviewClaimCreate,
    InterviewClaimUpdate,
    InterviewProfileUpdate,
    PushSettingsUpdate,
    ReviewCardCreate,
    ReviewCardUpdate,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    TrainingAttemptResponse,
    TrainingProgressResponse,
    TrainingPromptResponse,
)
from app.config import settings
from app.interview.model_roles import resolve_model_role
from app.interview.progress import build_progress_payload
from app.interview.learning_path import comic_url_for_topic
from app.interview.plan_service import (
    generate_learning_plan,
    get_learning_doc_for_date,
    get_learning_plan,
    get_today_plan,
    list_learning_docs,
    push_settings_response,
    set_learning_day_status,
    update_push_settings,
)
from app.interview.orchestrator import TrainingOrchestrator, evaluate_with_optional_reflect
from app.interview.question_bank_retrieval import QuestionBankRetrieval
from app.interview.resume_craft import (
    build_polish_system_prompt,
    WINDOW_DAYS,
    build_resume_draft,
    check_eligibility,
    polish_or_template,
)
from app.interview.contextual_hint import (
    build_hint_messages,
    has_submitted_evaluation,
    latest_answer_text,
    resolve_contextual_hint,
)
from app.interview.training import (
    build_training_prompt,
    evaluate_answer,
    hint_for,
    normalize_level,
    pick_starter_topic,
    topics_for_role,
)

PROJECT_SIM_STRUCTURE_HINT = (
    "建议按 STAR 结构口述（不必背稿）：Situation → Task → Action → Result；"
    "本题请主动覆盖「方案取舍」与「项目证据」，不要只背定义。"
)
GUIDE_SOURCE_SUBSTR = "ai-agent-interview-guide"
PROJECT_QA_SECTION_SUBSTR = "06-面试问答集"
from app.models.database import (
    InterviewClaim,
    InterviewProfile,
    InterviewReviewCard,
    InterviewSessionEvent,
    InterviewTrainingAttempt,
)


logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _utcnow()).isoformat()


class InterviewService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_profile(self, user_id: UUID) -> InterviewProfile:
        result = await self.db.execute(
            select(InterviewProfile).where(InterviewProfile.user_id == str(user_id))
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            profile = InterviewProfile(user_id=str(user_id), keywords=[])
            self.db.add(profile)
            await self.db.commit()
            await self.db.refresh(profile)
        return profile

    async def update_profile(self, user_id: UUID, data: InterviewProfileUpdate) -> InterviewProfile:
        profile = await self.get_or_create_profile(user_id)
        old_deadline = profile.target_deadline
        old_role = (profile.target_role or "").strip() or None
        payload = data.model_dump(exclude_unset=True)
        for field, value in payload.items():
            setattr(profile, field, value)
        await self.db.commit()
        await self.db.refresh(profile)
        new_role = (profile.target_role or "").strip() or None
        role_changed = "target_role" in payload and new_role != old_role
        deadline_changed = (
            profile.target_deadline is not None and profile.target_deadline != old_deadline
        )
        if profile.target_deadline and (deadline_changed or role_changed):
            if role_changed:
                # Drop stale curriculum (e.g. 前端 React 巩固日) before rebuild.
                profile.learning_plan = {}
                await self.db.commit()
            await generate_learning_plan(self.db, profile)
        return profile

    async def get_learning_plan(self, user_id: UUID):
        profile = await self.get_or_create_profile(user_id)
        return await get_learning_plan(self.db, profile)

    async def regenerate_learning_plan(self, user_id: UUID):
        profile = await self.get_or_create_profile(user_id)
        return await generate_learning_plan(self.db, profile)

    async def get_today_plan(self, user_id: UUID, *, force_refresh: bool = False):
        profile = await self.get_or_create_profile(user_id)
        return await get_today_plan(self.db, profile, force_refresh=force_refresh)

    async def list_learning_docs(self, user_id: UUID):
        profile = await self.get_or_create_profile(user_id)
        return list_learning_docs(profile)

    async def get_learning_doc_for_date(
        self, user_id: UUID, iso_date: str, *, force_refresh: bool = False
    ):
        profile = await self.get_or_create_profile(user_id)
        return await get_learning_doc_for_date(
            self.db, profile, iso_date, force_refresh=force_refresh
        )

    async def set_learning_day_status(self, user_id: UUID, iso_date: str, *, status: str):
        profile = await self.get_or_create_profile(user_id)
        return await set_learning_day_status(self.db, profile, iso_date, status=status)

    async def get_push_settings(self, user_id: UUID):
        profile = await self.get_or_create_profile(user_id)
        return push_settings_response(profile)

    async def update_push_settings(self, user_id: UUID, data: PushSettingsUpdate):
        profile = await self.get_or_create_profile(user_id)
        return await update_push_settings(self.db, profile, data)

    async def list_claims(self, user_id: UUID) -> list[InterviewClaim]:
        profile = await self.get_or_create_profile(user_id)
        result = await self.db.execute(
            select(InterviewClaim)
            .where(InterviewClaim.profile_id == profile.id)
            .order_by(InterviewClaim.created_at.desc())
        )
        return list(result.scalars())

    async def add_claim(self, user_id: UUID, data: InterviewClaimCreate) -> InterviewClaim:
        profile = await self.get_or_create_profile(user_id)
        claim = InterviewClaim(profile_id=profile.id, **data.model_dump())
        self.db.add(claim)
        await self.db.commit()
        await self.db.refresh(claim)
        return claim

    async def update_claim(
        self, user_id: UUID, claim_id: UUID, data: InterviewClaimUpdate
    ) -> InterviewClaim | None:
        profile = await self.get_or_create_profile(user_id)
        result = await self.db.execute(
            select(InterviewClaim).where(
                InterviewClaim.id == str(claim_id), InterviewClaim.profile_id == profile.id
            )
        )
        claim = result.scalar_one_or_none()
        if claim is None:
            return None
        claim.status = data.status
        await self.db.commit()
        await self.db.refresh(claim)
        return claim

    async def add_review_card(self, user_id: UUID, data: ReviewCardCreate) -> InterviewReviewCard:
        profile = await self.get_or_create_profile(user_id)
        card = InterviewReviewCard(
            profile_id=profile.id,
            **data.model_dump(),
            status="new",
            next_due_at=_utcnow() + timedelta(days=1),
            source_claim_ids=[],
        )
        self.db.add(card)
        await self.db.commit()
        await self.db.refresh(card)
        return card

    async def list_review_cards(
        self, user_id: UUID, *, due_only: bool = False
    ) -> list[InterviewReviewCard]:
        profile = await self.get_or_create_profile(user_id)
        stmt = select(InterviewReviewCard).where(InterviewReviewCard.profile_id == profile.id)
        if due_only:
            stmt = stmt.where(
                InterviewReviewCard.next_due_at.is_not(None),
                InterviewReviewCard.next_due_at <= _utcnow(),
                InterviewReviewCard.status.in_(["new", "learning", "reviewing"]),
            )
        result = await self.db.execute(
            stmt.order_by(
                InterviewReviewCard.next_due_at.is_(None),
                InterviewReviewCard.next_due_at.asc(),
                InterviewReviewCard.created_at.desc(),
            ).limit(40)
        )
        return list(result.scalars())

    async def update_review_card(
        self, user_id: UUID, card_id: UUID, data: ReviewCardUpdate
    ) -> InterviewReviewCard | None:
        profile = await self.get_or_create_profile(user_id)
        result = await self.db.execute(
            select(InterviewReviewCard).where(
                InterviewReviewCard.id == str(card_id),
                InterviewReviewCard.profile_id == profile.id,
            )
        )
        card = result.scalar_one_or_none()
        if card is None:
            return None
        if data.status is not None:
            card.status = data.status
        if data.mark_reviewed:
            card.last_reviewed_at = _utcnow()
            card.status = card.status if card.status != "new" else "learning"
            card.next_due_at = _utcnow() + timedelta(days=3)
            card.successful_recall_count = int(card.successful_recall_count or 0) + 1
        await self.db.commit()
        await self.db.refresh(card)
        return card

    async def next_training_prompt(
        self, user_id: UUID, level: str | None = None, topic: str | None = None
    ) -> TrainingPromptResponse:
        prompt, _claim_ids, bank = await self._build_prompt(user_id, level=level, topic=topic)
        return prompt.model_copy(update={"starter_topics": bank})

    async def _build_prompt(
        self,
        user_id: UUID,
        level: str | None = None,
        topic: str | None = None,
        exclude_questions: list[str] | None = None,
        exclude_topics: list[str] | None = None,
        mode: str = "standard",
    ) -> tuple[TrainingPromptResponse, list[str], list[str]]:
        profile = await self.get_or_create_profile(user_id)
        claims = [c for c in await self.list_claims(user_id) if c.status == "confirmed"]
        cards = await self.list_review_cards(user_id)
        practiced = {card.topic for card in cards}
        requested = (topic or "").strip() or None
        excluded_q = {q.strip() for q in (exclude_questions or []) if q and q.strip()}
        excluded_t = {t.strip() for t in (exclude_topics or []) if t and t.strip()}
        project_sim = mode == "project_sim"

        route_level = normalize_level(
            level or profile.target_level,
            fallback=normalize_level(profile.target_level, "P6"),
        )
        role = profile.target_role
        difficulty = profile.target_level or route_level
        salary = profile.salary_band
        bank = list(topics_for_role(role))
        source_claim_ids: list[str] = []

        prompt_kwargs = {
            "level": route_level,
            "role": role,
            "difficulty": difficulty,
            "salary_band": salary,
            "practiced_topics": practiced,
        }

        selected_topic: str
        category: str
        if project_sim:
            category = "project"
            selected_topic = requested or "Agent"
            if selected_topic not in bank and "Agent" in bank:
                selected_topic = "Agent"
        elif requested:
            matched = next((c for c in claims if c.label == requested), None)
            category = (
                matched.category
                if matched and matched.category in {"skill", "project", "role"}
                else "skill"
            )
            if matched:
                source_claim_ids = [matched.id]
            selected_topic = requested
        elif claims:
            projects = [c for c in claims if c.category == "project"]
            roles = [c for c in claims if c.category == "role"]
            skills = [c for c in claims if c.category == "skill"]
            role_aligned = [c for c in skills if c.label in bank] or skills
            pool = projects or roles or role_aligned or claims
            unpracticed = [c for c in pool if c.label not in practiced]
            base = unpracticed or pool
            rotated = [c for c in base if c.label not in excluded_t] or list(base)
            selected = rotated[0]
            category = (
                selected.category if selected.category in {"skill", "project", "role"} else "skill"
            )
            source_claim_ids = [selected.id]
            selected_topic = selected.label
        else:
            category = "skill"
            selected_topic = pick_starter_topic(
                practiced, role=role, exclude_topics=excluded_t
            )

        question_override: str | None = None
        question_source: dict[str, str | None] | None = None
        retrieval_meta: dict | None = None
        retriever = QuestionBankRetrieval(self.db)
        orch = TrainingOrchestrator(retriever=retriever)

        if project_sim or category == "skill":
            if project_sim:
                focus_hint = "Evidence" if route_level == "P7" else "Trade-off"
            else:
                focus_hint = (
                    "Trade-off"
                    if route_level == "P6"
                    else ("Evidence" if route_level == "P7" else "Position")
                )
            retrieved = await orch.retrieve_question(
                role=role,
                topic=selected_topic,
                level=route_level,
                focus_node=focus_hint,
                exclude_questions=excluded_q,
                prefer_source_url_substr=GUIDE_SOURCE_SUBSTR if project_sim else None,
                prefer_source_section_substr=PROJECT_QA_SECTION_SUBSTR if project_sim else None,
            )
            if retrieved and retrieved.question not in excluded_q:
                question_override = retrieved.question
                question_source = {
                    "source_url": retrieved.source_url,
                    "source_title": retrieved.source_title,
                    "source_section": retrieved.source_section,
                }
                retrieval_meta = orch.retrieval_span(retrieved)
            # Project sim: if preferred section empty, still take any guide Agent Q
            if project_sim and not question_override:
                retrieved = await orch.retrieve_question(
                    role=role,
                    topic=selected_topic,
                    level=route_level,
                    focus_node=focus_hint,
                    exclude_questions=excluded_q,
                    prefer_source_url_substr=GUIDE_SOURCE_SUBSTR,
                )
                if retrieved and retrieved.question not in excluded_q:
                    question_override = retrieved.question
                    question_source = {
                        "source_url": retrieved.source_url,
                        "source_title": retrieved.source_title,
                        "source_section": retrieved.source_section,
                    }
                    retrieval_meta = orch.retrieval_span(retrieved)

        prompt = build_training_prompt(
            topic=selected_topic,
            category=category,
            question_override=question_override,
            **prompt_kwargs,
        )
        # If static fallback still produced the excluded question, try another starter topic once.
        if prompt.question in excluded_q and not requested and not project_sim:
            alt_topic = pick_starter_topic(
                practiced | {selected_topic},
                role=role,
                exclude_topics=excluded_t | {selected_topic},
            )
            if alt_topic != selected_topic:
                selected_topic = alt_topic
                retrieved = await orch.retrieve_question(
                    role=role,
                    topic=selected_topic,
                    level=route_level,
                    focus_node=(
                        "Trade-off"
                        if route_level == "P6"
                        else ("Evidence" if route_level == "P7" else "Position")
                    ),
                    exclude_questions=excluded_q,
                )
                question_override = (
                    retrieved.question
                    if retrieved and retrieved.question not in excluded_q
                    else None
                )
                question_source = (
                    {
                        "source_url": retrieved.source_url,
                        "source_title": retrieved.source_title,
                        "source_section": retrieved.source_section,
                    }
                    if retrieved and question_override
                    else None
                )
                if question_override:
                    retrieval_meta = orch.retrieval_span(retrieved)
                prompt = build_training_prompt(
                    topic=selected_topic,
                    category="skill",
                    question_override=question_override,
                    **prompt_kwargs,
                )

        focus_node = prompt.focus_node
        missing_nodes = list(prompt.missing_nodes)
        if project_sim:
            # Force depth nodes for project simulation
            focus_node = "Evidence" if route_level == "P7" else "Trade-off"
            for node in ("Trade-off", "Evidence"):
                if node not in missing_nodes:
                    missing_nodes.append(node)
        else:
            for card in cards:
                if card.topic == prompt.topic and card.missing_nodes:
                    missing_nodes = list(card.missing_nodes)
                    focus_node = str(card.missing_nodes[0])
                    break

        dto = TrainingPromptResponse(
            topic=prompt.topic,
            question=prompt.question,
            atlas=prompt.atlas,
            route_nodes=prompt.route_nodes,
            missing_nodes=missing_nodes,
            level=prompt.level,  # type: ignore[arg-type]
            category=prompt.category,  # type: ignore[arg-type]
            focus_node=focus_node,
            starter_topics=bank,
            target_role=role,
            target_level=difficulty,
            salary_band=salary,
            question_source=question_source,
            retrieval=retrieval_meta,
        )
        return dto, source_claim_ids, bank

    def evaluate(self, data: EvaluateAnswerRequest) -> EvaluateAnswerResponse:
        result = evaluate_answer(data.answer, focus_node=data.focus_node)
        hint = result.get("hint")
        return EvaluateAnswerResponse(
            covered_nodes=list(result["covered_nodes"]),  # type: ignore[arg-type]
            missing_nodes=list(result["missing_nodes"]),  # type: ignore[arg-type]
            breakpoint=result.get("breakpoint"),  # type: ignore[arg-type]
            hint=HintPayload(**hint) if isinstance(hint, dict) else None,
            next_step=str(result["next_step"]),
            complete=bool(result["complete"]),
        )

    def progressive_hint(self, data: HintRequest) -> HintResponse:
        payload = hint_for(data.node, data.level)
        return HintResponse(level=payload["level"], content=payload["content"])

    async def _next_event_seq(self, profile_id: str) -> int:
        result = await self.db.execute(
            select(func.coalesce(func.max(InterviewSessionEvent.seq), 0)).where(
                InterviewSessionEvent.profile_id == profile_id
            )
        )
        return int(result.scalar_one()) + 1

    async def _append_event(
        self,
        profile_id: str,
        attempt_id: str | None,
        event_type: str,
        payload: dict | None = None,
    ) -> None:
        seq = await self._next_event_seq(profile_id)
        self.db.add(
            InterviewSessionEvent(
                profile_id=profile_id,
                attempt_id=attempt_id,
                seq=seq,
                type=event_type,
                payload=payload or {},
            )
        )

    def _attempt_to_response(
        self,
        attempt: InterviewTrainingAttempt,
        *,
        resumed: bool = False,
        starter_topics: list[str] | None = None,
    ) -> TrainingAttemptResponse:
        evaluation = None
        if attempt.evaluation:
            evaluation = EvaluationTrace.model_validate(attempt.evaluation)
        answers = [
            AnswerVersionPayload(
                version=int(item.get("version", 0)),
                text=str(item.get("text", "")),
                created_at=str(item.get("created_at", "")),
            )
            for item in (attempt.answers or [])
        ]
        missing = list(evaluation.missing_nodes) if evaluation else list(attempt.route_nodes or [])
        snap = dict(attempt.goal_snapshot or {})
        training_mode = str(snap.get("training_mode") or "standard")
        if training_mode not in {"standard", "project_sim"}:
            training_mode = "standard"
        return TrainingAttemptResponse(
            id=attempt.id,
            status=attempt.status,  # type: ignore[arg-type]
            topic=attempt.topic,
            question=attempt.question,
            atlas=list(attempt.atlas or []),
            route_nodes=list(attempt.route_nodes or []),
            missing_nodes=missing,
            level=attempt.level,  # type: ignore[arg-type]
            category=attempt.category,  # type: ignore[arg-type]
            focus_node=attempt.focus_node,
            goal_snapshot=snap,
            source_claim_ids=list(attempt.source_claim_ids or []),
            answers=answers,
            evaluation=evaluation,
            hint_level=int(attempt.hint_level or 0),
            review_card_id=attempt.review_card_id,
            degraded_reason=attempt.degraded_reason,
            resumed=resumed,
            starter_topics=starter_topics or [],
            structure_hint=str(snap["structure_hint"]) if snap.get("structure_hint") else None,
            comic_url=comic_url_for_topic(attempt.topic),
            training_mode=training_mode,  # type: ignore[arg-type]
            created_at=attempt.created_at,
            updated_at=attempt.updated_at,
        )

    async def get_active_attempt(self, user_id: UUID) -> TrainingAttemptResponse | None:
        profile = await self.get_or_create_profile(user_id)
        result = await self.db.execute(
            select(InterviewTrainingAttempt)
            .where(
                InterviewTrainingAttempt.profile_id == profile.id,
                InterviewTrainingAttempt.status.in_(list(ACTIVE_STATUSES)),
            )
            .order_by(InterviewTrainingAttempt.updated_at.desc())
            .limit(1)
        )
        attempt = result.scalar_one_or_none()
        if attempt is None:
            return None
        bank = list(topics_for_role(profile.target_role))
        return self._attempt_to_response(attempt, resumed=True, starter_topics=bank)

    async def create_or_resume_attempt(
        self, user_id: UUID, data: CreateAttemptRequest | None = None
    ) -> TrainingAttemptResponse:
        profile = await self.get_or_create_profile(user_id)
        active = await self.get_active_attempt(user_id)
        if active is not None:
            if active_attempt_matches_goal(
                active.goal_snapshot,
                target_role=profile.target_role,
                target_level=profile.target_level,
                salary_band=getattr(profile, "salary_band", None),
            ):
                return active.model_copy(update={"resumed": True})
            # Profile goal changed (e.g. 全栈 → AI 应用工程) — drop stale attempt.
            await self.abandon_attempt(
                user_id, active.id, AbandonAttemptRequest(reason="switch_topic")
            )

        data = data or CreateAttemptRequest()
        mode = data.mode or "standard"
        prompt, claim_ids, bank = await self._build_prompt(
            user_id,
            level=data.level,
            topic=data.topic,
            exclude_questions=list(data.exclude_questions or []),
            exclude_topics=list(data.exclude_topics or []),
            mode=mode,
        )
        goal_snapshot = {
            "target_role": prompt.target_role,
            "target_level": prompt.target_level,
            "salary_band": prompt.salary_band,
            "question_source": prompt.question_source,
            "training_mode": mode,
            "retrieval": prompt.retrieval,
        }
        if mode == "project_sim":
            goal_snapshot["structure_hint"] = PROJECT_SIM_STRUCTURE_HINT
        attempt = InterviewTrainingAttempt(
            profile_id=profile.id,
            topic=prompt.topic,
            question=prompt.question,
            level=prompt.level,
            focus_node=prompt.focus_node,
            route_nodes=list(prompt.route_nodes),
            atlas=list(prompt.atlas),
            category=prompt.category,
            goal_snapshot=goal_snapshot,
            source_claim_ids=claim_ids,
            status="open",
            answers=[],
            evaluation=None,
            hint_level=0,
        )
        self.db.add(attempt)
        await self.db.flush()
        await self._append_event(
            profile.id,
            attempt.id,
            "attempt_started",
            {
                "topic": attempt.topic,
                "retrieval": prompt.retrieval,
            },
        )
        await self.db.commit()
        await self.db.refresh(attempt)
        return self._attempt_to_response(attempt, starter_topics=bank)

    async def _get_owned_attempt(
        self, user_id: UUID, attempt_id: UUID
    ) -> InterviewTrainingAttempt:
        profile = await self.get_or_create_profile(user_id)
        result = await self.db.execute(
            select(InterviewTrainingAttempt).where(
                InterviewTrainingAttempt.id == str(attempt_id),
                InterviewTrainingAttempt.profile_id == profile.id,
            )
        )
        attempt = result.scalar_one_or_none()
        if attempt is None:
            raise HTTPException(status_code=404, detail="Training attempt not found")
        return attempt

    def _build_trace(self, result: dict, *, retrieval: dict | None = None) -> dict:
        hint = result.get("hint")
        return {
            "covered_nodes": list(result["covered_nodes"]),
            "missing_nodes": list(result["missing_nodes"]),
            "breakpoint": result.get("breakpoint"),
            "hint": hint if isinstance(hint, dict) else None,
            "next_step": str(result["next_step"]),
            "complete": bool(result["complete"]),
            "deterministic": result.get("deterministic")
            or {
                "rule_version": RULE_VERSION,
                "signals_hit": result.get("signals_hit") or {},
            },
            "llm": result.get("llm"),
            "retrieval": result.get("retrieval") if result.get("retrieval") is not None else retrieval,
            "status": str(result.get("status") or "ok"),
            "evaluated_at": _iso(),
        }

    async def submit_answer(
        self, user_id: UUID, attempt_id: UUID, data: SubmitAnswerRequest
    ) -> SubmitAnswerResponse:
        attempt = await self._get_owned_attempt(user_id, attempt_id)
        if not can_submit_version(attempt.status, data.version):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot submit v{data.version} from status={attempt.status}",
            )

        answers = list(attempt.answers or [])
        answers = [a for a in answers if int(a.get("version", 0)) != data.version]
        answers.append(
            {"version": data.version, "text": data.text.strip(), "created_at": _iso()}
        )
        attempt.answers = answers
        attempt.status = after_answer_status(data.version)
        attempt.degraded_reason = None
        await self._append_event(
            attempt.profile_id,
            attempt.id,
            "answer_submitted",
            {"version": data.version},
        )

        degraded = False
        retrieval = None
        snap = dict(attempt.goal_snapshot or {})
        if isinstance(snap.get("retrieval"), dict):
            retrieval = snap["retrieval"]
        try:
            raw = evaluate_with_optional_reflect(
                answer=data.text,
                focus_node=attempt.focus_node,
                question=attempt.question,
                route_nodes=list(attempt.route_nodes or []),
                enable_llm_reflect=False,
                retrieval_span=retrieval,
            )
            trace = self._build_trace(raw, retrieval=retrieval)
            attempt.evaluation = trace
            attempt.status = "reanswered" if data.version == 2 else "evaluated"
            if isinstance(trace.get("breakpoint"), str):
                attempt.focus_node = str(trace["breakpoint"])
            await self._append_event(
                attempt.profile_id,
                attempt.id,
                "evaluation_completed",
                {
                    "version": data.version,
                    "complete": bool(trace.get("complete")),
                    "breakpoint": trace.get("breakpoint"),
                    "retrieval_mode": (retrieval or {}).get("mode") if retrieval else None,
                },
            )
        except Exception:  # noqa: BLE001 — isolate evaluator failures
            degraded = True
            attempt.status = "degraded"
            attempt.degraded_reason = "evaluator_exception"
            await self._append_event(
                attempt.profile_id,
                attempt.id,
                "evaluation_failed",
                {"version": data.version, "reason": "evaluator_exception"},
            )

        await self.db.commit()
        await self.db.refresh(attempt)
        profile = await self.get_or_create_profile(user_id)
        bank = list(topics_for_role(profile.target_role))
        return SubmitAnswerResponse(
            attempt=self._attempt_to_response(attempt, starter_topics=bank),
            degraded=degraded,
        )

    async def attempt_hint(
        self, user_id: UUID, attempt_id: UUID, data: AttemptHintRequest
    ) -> HintResponse:
        attempt = await self._get_owned_attempt(user_id, attempt_id)
        if attempt.status not in ACTIVE_STATUSES:
            raise HTTPException(status_code=409, detail="Attempt is terminal")
        answers = list(attempt.answers or [])
        evaluation = attempt.evaluation if isinstance(attempt.evaluation, dict) else None
        level = min(max(data.level, 1), 4)
        post_submit = has_submitted_evaluation(answers=answers, evaluation=evaluation)
        if post_submit and evaluation is not None:
            node = str(evaluation.get("breakpoint") or attempt.focus_node or "Position")
            covered = [str(x) for x in (evaluation.get("covered_nodes") or [])]
            missing = [str(x) for x in (evaluation.get("missing_nodes") or [])]
            breakpoint = str(evaluation.get("breakpoint") or "") or None
            answer_text = latest_answer_text(answers)
        else:
            node = str(attempt.focus_node or "Position")
            covered = []
            missing = []
            breakpoint = None
            answer_text = ""

        llm_text = await self._maybe_contextual_hint_llm(
            topic=str(attempt.topic),
            question=str(attempt.question),
            answer=answer_text,
            breakpoint=breakpoint,
            covered_nodes=covered,
            missing_nodes=missing,
            level=level,
            focus_node=str(attempt.focus_node or "Position"),
        )
        payload, source = resolve_contextual_hint(
            topic=str(attempt.topic),
            node=node,
            level=level,
            llm_text=llm_text,
            question=str(attempt.question),
        )
        attempt.hint_level = level
        await self._append_event(
            attempt.profile_id,
            attempt.id,
            "hint_shown",
            {
                "level": level,
                "node": node,
                "source": source,
                "mode": "post_submit" if post_submit else "pre_submit",
            },
        )
        await self.db.commit()
        return HintResponse(level=payload["level"], content=payload["content"])

    async def _maybe_contextual_hint_llm(
        self,
        *,
        topic: str,
        question: str,
        answer: str,
        breakpoint: str | None,
        covered_nodes: list[str],
        missing_nodes: list[str],
        level: int,
        focus_node: str | None = None,
    ) -> str | None:
        role = resolve_model_role("hint")
        if role.provider_hint == "rules":
            return None
        base_url = (
            (settings.INTERVIEW_HINT_BASE_URL or "").rstrip("/")
            or (settings.INTERVIEW_RESUME_CRAFT_BASE_URL or "").rstrip("/")
        )
        if not base_url:
            return None
        url = f"{base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        api_key = settings.INTERVIEW_HINT_API_KEY or settings.INTERVIEW_RESUME_CRAFT_API_KEY or ""
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        messages = build_hint_messages(
            topic=topic,
            question=question,
            answer=answer,
            breakpoint=breakpoint,
            covered_nodes=covered_nodes,
            missing_nodes=missing_nodes,
            level=level,
            focus_node=focus_node,
        )
        payload = {
            "model": role.model_id,
            "temperature": role.temperature,
            "messages": messages,
        }
        try:
            # trust_env=False: avoid corporate/system HTTP(S)_PROXY 403 on DeepSeek
            async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            message = data["choices"][0]["message"]
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                # some reasoning models may park text elsewhere
                alt = message.get("reasoning_content")
                content = alt if isinstance(alt, str) else ""
            if not isinstance(content, str) or not content.strip():
                return None
            return content.strip()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "contextual_hint_llm_failed",
                extra={"error": f"{type(exc).__name__}: {exc}"},
            )
            return None

    async def commit_attempt(self, user_id: UUID, attempt_id: UUID) -> TrainingAttemptResponse:
        attempt = await self._get_owned_attempt(user_id, attempt_id)
        if not can_commit(attempt.status, list(attempt.answers or []), attempt.evaluation):
            raise HTTPException(
                status_code=409,
                detail="Commit requires answer v2, or a complete first evaluation",
            )
        if attempt.status == "degraded":
            raise HTTPException(status_code=409, detail="Cannot commit a degraded attempt")

        latest = ""
        for item in sorted(attempt.answers or [], key=lambda a: int(a.get("version", 0))):
            latest = str(item.get("text", ""))

        missing = list((attempt.evaluation or {}).get("missing_nodes") or [])
        card_id = None
        if missing:
            card = InterviewReviewCard(
                profile_id=attempt.profile_id,
                topic=attempt.topic,
                question=attempt.question,
                answer=latest or "(empty)",
                missing_nodes=missing,
                status="new",
                attempt_id=attempt.id,
                next_due_at=_utcnow() + timedelta(days=1),
                source_claim_ids=list(attempt.source_claim_ids or []),
            )
            self.db.add(card)
            await self.db.flush()
            card_id = card.id

        attempt.status = "committed"
        attempt.review_card_id = card_id
        await self._append_event(
            attempt.profile_id,
            attempt.id,
            "attempt_committed",
            {"review_card_id": card_id, "missing_count": len(missing)},
        )
        await self.db.commit()
        await self.db.refresh(attempt)
        profile = await self.get_or_create_profile(user_id)
        return self._attempt_to_response(
            attempt, starter_topics=list(topics_for_role(profile.target_role))
        )

    async def get_training_progress(self, user_id: UUID) -> TrainingProgressResponse:
        profile = await self.get_or_create_profile(user_id)
        role_topics = list(topics_for_role(profile.target_role))
        attempts = list(
            (
                await self.db.execute(
                    select(InterviewTrainingAttempt).where(
                        InterviewTrainingAttempt.profile_id == profile.id,
                        InterviewTrainingAttempt.status == "committed",
                    )
                )
            ).scalars()
        )
        cards = list(
            (
                await self.db.execute(
                    select(InterviewReviewCard).where(InterviewReviewCard.profile_id == profile.id)
                )
            ).scalars()
        )
        payload = build_progress_payload(
            target_role=profile.target_role,
            target_level=profile.target_level,
            salary_band=getattr(profile, "salary_band", None),
            role_topics=role_topics,
            committed_attempts=attempts,
            cards=cards,
        )
        return TrainingProgressResponse.model_validate(payload)

    async def _list_committed_attempts(
        self, profile_id: str, *, window_days: int = WINDOW_DAYS
    ) -> list[InterviewTrainingAttempt]:
        cutoff = _utcnow() - timedelta(days=window_days)
        result = await self.db.execute(
            select(InterviewTrainingAttempt).where(
                InterviewTrainingAttempt.profile_id == profile_id,
                InterviewTrainingAttempt.status == "committed",
                InterviewTrainingAttempt.updated_at >= cutoff,
            )
        )
        return list(result.scalars())

    async def _maybe_polish_resume(self, draft: dict) -> str | None:
        role = resolve_model_role("resume_craft")
        if role.provider_hint == "template":
            return None
        base_url = (settings.INTERVIEW_RESUME_CRAFT_BASE_URL or "").rstrip("/")
        if not base_url:
            return None
        url = f"{base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        api_key = settings.INTERVIEW_RESUME_CRAFT_API_KEY or ""
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": role.model_id,
            "temperature": role.temperature,
            "messages": [
                {"role": "system", "content": build_polish_system_prompt()},
                {
                    "role": "user",
                    "content": json.dumps(draft, ensure_ascii=False),
                },
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                return None
            return content
        except Exception as exc:  # noqa: BLE001
            logger.warning("resume_craft_polish_failed", extra={"error": str(exc)})
            return None

    async def resume_eligibility(self, user_id: UUID) -> dict:
        profile = await self.get_or_create_profile(user_id)
        claims = await self.list_claims(user_id)
        confirmed = [c for c in claims if c.status == "confirmed"]
        attempts = await self._list_committed_attempts(profile.id, window_days=WINDOW_DAYS)
        return check_eligibility(
            confirmed_claims=confirmed,
            committed_attempts_7d=len(attempts),
        )

    async def craft_resume(self, user_id: UUID) -> dict:
        profile = await self.get_or_create_profile(user_id)
        claims = [c for c in await self.list_claims(user_id) if c.status == "confirmed"]
        attempts = await self._list_committed_attempts(profile.id, window_days=WINDOW_DAYS)
        gate = check_eligibility(confirmed_claims=claims, committed_attempts_7d=len(attempts))
        if not gate["eligible"]:
            raise HTTPException(
                status_code=403,
                detail={"reasons": gate["reasons"], "stats": gate["stats"]},
            )
        draft = build_resume_draft(
            profile=profile, confirmed_claims=claims, committed_attempts=attempts
        )
        polished = await self._maybe_polish_resume(draft)
        markdown, warnings = polish_or_template(draft=draft, polished=polished)
        if not profile.target_role:
            warnings.append("未设置目标岗位，标题区已用占位")
        return {
            "markdown": markdown,
            "sources": {
                "claim_ids": [str(c.id) for c in claims],
                "attempt_ids": [str(a.id) for a in attempts],
            },
            "warnings": warnings,
        }

    async def abandon_attempt(
        self, user_id: UUID, attempt_id: UUID, data: AbandonAttemptRequest
    ) -> TrainingAttemptResponse:
        attempt = await self._get_owned_attempt(user_id, attempt_id)
        if not can_abandon(attempt.status):
            raise HTTPException(status_code=409, detail="Attempt already terminal")
        attempt.status = "abandoned"
        await self._append_event(
            attempt.profile_id,
            attempt.id,
            "attempt_abandoned",
            {"reason": data.reason},
        )
        await self.db.commit()
        await self.db.refresh(attempt)
        profile = await self.get_or_create_profile(user_id)
        return self._attempt_to_response(
            attempt, starter_topics=list(topics_for_role(profile.target_role))
        )
