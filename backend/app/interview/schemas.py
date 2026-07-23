"""Schemas for the low-input Interview Navigator."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


ClaimCategory = Literal["skill", "project", "role"]
ClaimStatus = Literal["candidate", "confirmed", "rejected"]
TrainingLevel = Literal["P5", "P6", "P7"]


class InterviewProfileUpdate(BaseModel):
    target_role: str | None = Field(default=None, max_length=120)
    target_level: str | None = Field(default=None, max_length=80)
    salary_band: str | None = Field(default=None, max_length=80)
    target_deadline: date | None = None
    keywords: list[str] = Field(default_factory=list, max_length=80)


class InterviewProfileResponse(BaseModel):
    id: str
    target_role: str | None
    target_level: str | None
    salary_band: str | None = None
    target_deadline: date | None = None
    keywords: list[str]
    updated_at: datetime


class InterviewClaimCreate(BaseModel):
    category: ClaimCategory
    label: str = Field(min_length=1, max_length=255)
    keywords: list[str] = Field(default_factory=list, max_length=30)


class InterviewClaimUpdate(BaseModel):
    status: ClaimStatus


class InterviewClaimResponse(BaseModel):
    id: str
    category: ClaimCategory
    label: str
    keywords: list[str]
    status: ClaimStatus
    created_at: datetime


class ResumeExtractionResponse(BaseModel):
    claims: list[InterviewClaimCreate]
    warning: str = "仅提取本地关键词与经历条目；简历原文不会保存或发送给模型。"


ReviewCardStatus = Literal["new", "learning", "reviewing", "deferred", "mastered", "invalidated"]
AttemptStatus = Literal[
    "open", "answering", "evaluated", "reanswered", "committed", "abandoned", "degraded"
]


class ReviewCardCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=255)
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    missing_nodes: list[str] = Field(default_factory=list, max_length=10)


class ReviewCardUpdate(BaseModel):
    status: ReviewCardStatus | None = None
    mark_reviewed: bool = False


class ReviewCardResponse(ReviewCardCreate):
    id: str
    created_at: datetime
    status: ReviewCardStatus = "new"
    attempt_id: str | None = None
    last_reviewed_at: datetime | None = None
    next_due_at: datetime | None = None
    successful_recall_count: int = 0
    source_claim_ids: list[str] = Field(default_factory=list)


class AnswerVersionPayload(BaseModel):
    version: int
    text: str
    created_at: str


class HintPayload(BaseModel):
    node: str
    recall: str
    keywords: str
    example: str


class EvaluationTrace(BaseModel):
    covered_nodes: list[str]
    missing_nodes: list[str]
    breakpoint: str | None
    hint: HintPayload | None = None
    next_step: str
    complete: bool
    deterministic: dict = Field(default_factory=dict)
    llm: dict | None = None
    retrieval: dict | None = None
    status: Literal["ok", "degraded"] = "ok"
    reason: str | None = None
    evaluated_at: str | None = None


class TrainingAttemptResponse(BaseModel):
    id: str
    status: AttemptStatus
    topic: str
    question: str
    atlas: list[str]
    route_nodes: list[str]
    missing_nodes: list[str] = Field(default_factory=list)
    level: TrainingLevel
    category: ClaimCategory
    focus_node: str
    goal_snapshot: dict = Field(default_factory=dict)
    source_claim_ids: list[str] = Field(default_factory=list)
    answers: list[AnswerVersionPayload] = Field(default_factory=list)
    evaluation: EvaluationTrace | None = None
    hint_level: int = 0
    review_card_id: str | None = None
    degraded_reason: str | None = None
    resumed: bool = False
    starter_topics: list[str] = Field(default_factory=list)
    structure_hint: str | None = None
    comic_url: str | None = None
    training_mode: Literal["standard", "project_sim"] = "standard"
    created_at: datetime
    updated_at: datetime


class ActiveAttemptResponse(BaseModel):
    attempt: TrainingAttemptResponse | None = None


class CreateAttemptRequest(BaseModel):
    topic: str | None = Field(default=None, max_length=255)
    level: TrainingLevel | None = None
    exclude_questions: list[str] = Field(default_factory=list)
    exclude_topics: list[str] = Field(default_factory=list)
    mode: Literal["standard", "project_sim"] = "standard"


class SubmitAnswerRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    version: Literal[1, 2] = 1


class SubmitAnswerResponse(BaseModel):
    attempt: TrainingAttemptResponse
    degraded: bool = False


class AttemptHintRequest(BaseModel):
    level: int = Field(default=1, ge=1, le=4)


class AbandonAttemptRequest(BaseModel):
    reason: Literal["skip_retry", "switch_topic", "change_question"] = "skip_retry"


class TrainingPromptResponse(BaseModel):
    topic: str
    question: str
    atlas: list[str]
    route_nodes: list[str]
    missing_nodes: list[str]
    level: TrainingLevel
    category: ClaimCategory
    focus_node: str
    starter_topics: list[str] = Field(default_factory=list)
    target_role: str | None = None
    target_level: str | None = None
    salary_band: str | None = None
    question_source: dict[str, str | None] | None = None
    retrieval: dict | None = None


class EvaluateAnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=4000)
    topic: str = Field(min_length=1, max_length=255)
    question: str = Field(min_length=1)
    focus_node: str | None = None
    level: TrainingLevel = "P6"


class EvaluateAnswerResponse(BaseModel):
    covered_nodes: list[str]
    missing_nodes: list[str]
    breakpoint: str | None
    hint: HintPayload | None = None
    next_step: str
    complete: bool


class HintRequest(BaseModel):
    node: str = Field(min_length=1, max_length=80)
    level: int = Field(default=1, ge=1, le=4)


class HintResponse(BaseModel):
    level: str
    content: str


class ProgressGoal(BaseModel):
    target_role: str | None = None
    target_level: str | None = None
    salary_band: str | None = None
    tier: Literal["low", "mid", "high"] = "mid"


class ProgressCoverage(BaseModel):
    covered_count: int
    total_count: int
    covered_topics: list[str]
    missing_topics: list[str]
    ratio: float


class ProgressRouteDepth(BaseModel):
    window_days: int
    committed_count: int
    tradeoff_hits: int
    evidence_hits: int
    tradeoff_rate: float
    evidence_rate: float
    avg_covered_nodes: float


class ProgressRetention(BaseModel):
    total_cards: int
    due_count: int
    consolidated_count: int
    stuck_count: int
    healthy_ratio: float


class ProgressExpectation(BaseModel):
    id: str
    label: str
    detail: str
    met: bool


class ProgressComposite(BaseModel):
    score: int
    uncapped_score: int
    formula: str
    cap_reason: str | None = None
    components: dict[str, float]


class ProgressWeekBucket(BaseModel):
    week_start: str
    committed_count: int
    tradeoff_rate: float
    evidence_rate: float


class LearningPathNextModule(BaseModel):
    stage_id: str | None = None
    title: str
    topic: str
    goal: str
    comic_url: str | None = None
    reason: str


class LearningPathStage(BaseModel):
    id: str
    title: str
    goal: str
    topics: list[str]
    primary_topic: str
    comic_url: str | None = None
    days_hint: str
    done: bool
    relevant: bool


class LearningPathProgress(BaseModel):
    stages: list[LearningPathStage]
    next_module: LearningPathNextModule
    done_count: int
    total_relevant: int


class TrainingProgressResponse(BaseModel):
    goal: ProgressGoal
    coverage: ProgressCoverage
    route_depth: ProgressRouteDepth
    retention: ProgressRetention
    expectations: list[ProgressExpectation]
    next_step: str
    learning_path: LearningPathProgress | None = None
    composite: ProgressComposite
    weekly_trend: list[ProgressWeekBucket]
    counted_rule: str


class ResumeEligibilityStats(BaseModel):
    confirmed_claims: int
    confirmed_project_like_claims: int
    committed_attempts_7d: int


class ResumeEligibilityResponse(BaseModel):
    eligible: bool
    reasons: list[str] = Field(default_factory=list)
    stats: ResumeEligibilityStats


class ResumeCraftSources(BaseModel):
    claim_ids: list[str] = Field(default_factory=list)
    attempt_ids: list[str] = Field(default_factory=list)


class ResumeCraftResponse(BaseModel):
    markdown: str
    sources: ResumeCraftSources
    warnings: list[str] = Field(default_factory=list)


PlanTaskType = Literal["train", "review", "consolidate"]


class PlanDayTask(BaseModel):
    date: str
    task_type: PlanTaskType
    stage_id: str | None = None
    title: str
    topic: str
    goal: str
    message: str
    doc_title: str | None = None
    section_title: str | None = None
    reading_bullets: list[str] = Field(default_factory=list)
    comic_url: str | None = None
    unit_keys: list[str] = Field(default_factory=list)
    units_packed: int = 1
    learning_status: Literal["pending", "completed"] = "pending"
    completed_at: str | None = None


class TodayLearningDoc(BaseModel):
    doc_title: str
    section_title: str
    topic: str
    reading_bullets: list[str] = Field(default_factory=list)
    comic_url: str | None = None
    bank_excerpts: list[str] = Field(default_factory=list)
    markdown_body: str | None = None
    today_goal: str | None = None
    practice_task: str | None = None
    source_links: list[dict[str, str]] = Field(default_factory=list)
    generated_by: Literal["llm", "template"] = "template"
    format_version: str = "qa_v1"


class TodayPlanResponse(BaseModel):
    date: str
    tasks: list[PlanDayTask] = Field(default_factory=list)
    due_review_count: int = 0
    push_message: str | None = None
    has_plan: bool = False
    push_due_today: bool = False
    learning_doc: TodayLearningDoc | None = None
    active_date: str | None = None
    learning_status: Literal["pending", "completed"] | None = None
    is_backlog: bool = False
    incomplete_count: int = 0
    units_packed: int = 1


class LearningDocHistoryItem(BaseModel):
    date: str
    topic: str
    title: str
    section_title: str | None = None
    task_type: PlanTaskType = "train"
    has_doc: bool = False
    generated_by: Literal["llm", "template"] | None = None
    is_today: bool = False
    learning_status: Literal["pending", "completed"] = "pending"
    is_active: bool = False
    units_packed: int = 1


class LearningDocHistoryResponse(BaseModel):
    items: list[LearningDocHistoryItem] = Field(default_factory=list)
    has_plan: bool = False


class LearningDocByDateResponse(BaseModel):
    date: str
    learning_doc: TodayLearningDoc
    task: PlanDayTask | None = None


class LearningDayStatusUpdate(BaseModel):
    status: Literal["pending", "completed"] = "completed"


class LearningDayStatusResponse(BaseModel):
    date: str
    learning_status: Literal["pending", "completed"]
    completed_at: str | None = None
    active_date: str | None = None
    incomplete_count: int = 0


class LearningDocAskRequest(BaseModel):
    quote: str = Field(..., min_length=2, max_length=4000)
    question: str = Field(default="", max_length=1000)
    topic: str | None = Field(default=None, max_length=120)
    section_title: str | None = Field(default=None, max_length=200)
    doc_date: str | None = Field(default=None, max_length=32)


class LearningDocAskResponse(BaseModel):
    answer: str
    quote: str
    question: str
    generated_by: Literal["llm", "template"] = "template"


class LearningPlanResponse(BaseModel):
    deadline: str | None = None
    start_date: str | None = None
    total_days: int = 0
    days: list[PlanDayTask] = Field(default_factory=list)
    summary: str = ""
    feasible: bool = True
    default_span_days: int | None = None
    plan_generated_at: datetime | None = None
    days_remaining: int | None = None
    max_units_per_day: int | None = None


PushFrequency = Literal["daily", "weekdays", "weekends"]


class PushSettingsUpdate(BaseModel):
    push_enabled: bool | None = None
    push_time: str | None = None
    push_timezone: str | None = Field(default=None, max_length=64)
    push_frequency: PushFrequency | None = None

    @field_validator("push_time", mode="before")
    @classmethod
    def validate_push_time(cls, value: object) -> str | None:
        if value is None:
            return None
        raw = str(value).strip()
        if not raw:
            return None
        # Browsers may emit HH:MM:SS from <input type="time">.
        parts = raw.split(":")
        if len(parts) < 2:
            raise ValueError("push_time must be a valid HH:MM")
        hour, minute = int(parts[0]), int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("push_time must be a valid HH:MM")
        return f"{hour:02d}:{minute:02d}"


class PushSettingsResponse(BaseModel):
    push_enabled: bool
    push_time: str
    push_timezone: str
    push_frequency: PushFrequency = "weekdays"
    target_deadline: date | None = None
    last_push_date: date | None = None


class SttStatusResponse(BaseModel):
    enabled: bool


class TranscribeResponse(BaseModel):
    text: str
