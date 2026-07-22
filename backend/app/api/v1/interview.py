"""Interview Navigator profile and training-attempt APIs."""

from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user_auth, get_db
from app.interview.schemas import (
    AbandonAttemptRequest,
    ActiveAttemptResponse,
    AttemptHintRequest,
    CreateAttemptRequest,
    EvaluateAnswerRequest,
    EvaluateAnswerResponse,
    HintRequest,
    HintResponse,
    InterviewClaimCreate,
    InterviewClaimResponse,
    InterviewClaimUpdate,
    InterviewProfileResponse,
    InterviewProfileUpdate,
    ResumeCraftResponse,
    ResumeEligibilityResponse,
    ResumeExtractionResponse,
    ReviewCardCreate,
    ReviewCardResponse,
    ReviewCardUpdate,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    TrainingAttemptResponse,
    TrainingProgressResponse,
    TrainingPromptResponse,
)
from app.interview.resume_extract import extract_resume_claims, extract_resume_text
from app.interview.services import InterviewService

router = APIRouter(prefix="/interview", tags=["interview"])

MAX_RESUME_SIZE = 5 * 1024 * 1024


def _profile_response(profile) -> InterviewProfileResponse:
    return InterviewProfileResponse(
        id=profile.id,
        target_role=profile.target_role,
        target_level=profile.target_level,
        salary_band=getattr(profile, "salary_band", None),
        keywords=profile.keywords,
        updated_at=profile.updated_at,
    )


def _claim_response(claim) -> InterviewClaimResponse:
    return InterviewClaimResponse(
        id=claim.id,
        category=claim.category,
        label=claim.label,
        keywords=claim.keywords,
        status=claim.status,
        created_at=claim.created_at,
    )


def _card_response(card) -> ReviewCardResponse:
    return ReviewCardResponse(
        id=card.id,
        topic=card.topic,
        question=card.question,
        answer=card.answer,
        missing_nodes=card.missing_nodes,
        created_at=card.created_at,
        status=getattr(card, "status", None) or "new",
        attempt_id=getattr(card, "attempt_id", None),
        last_reviewed_at=getattr(card, "last_reviewed_at", None),
        next_due_at=getattr(card, "next_due_at", None),
        successful_recall_count=int(getattr(card, "successful_recall_count", 0) or 0),
        source_claim_ids=list(getattr(card, "source_claim_ids", None) or []),
    )


@router.post("/resume/extract", response_model=ResumeExtractionResponse)
async def extract_resume(
    file: UploadFile = File(...),
    _: UUID = Depends(get_current_user_auth),
):
    """Extract minimal local-only resume claims without storing the original file."""
    if file.content_type not in {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }:
        raise HTTPException(status_code=400, detail="仅支持 PDF 或 DOCX 简历")
    content = await file.read(MAX_RESUME_SIZE + 1)
    if len(content) > MAX_RESUME_SIZE:
        raise HTTPException(status_code=400, detail="简历文件不能超过 5MB")
    try:
        text = extract_resume_text(content, file.content_type)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="无法读取该简历文件") from exc
    return ResumeExtractionResponse(
        claims=[InterviewClaimCreate(**claim) for claim in extract_resume_claims(text)]
    )


@router.get("/resume/eligibility", response_model=ResumeEligibilityResponse)
async def resume_eligibility(
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    data = await InterviewService(db).resume_eligibility(user_id)
    return ResumeEligibilityResponse(**data)


@router.post("/resume/craft", response_model=ResumeCraftResponse)
async def craft_resume(
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    data = await InterviewService(db).craft_resume(user_id)
    return ResumeCraftResponse(**data)


@router.get("/profile", response_model=InterviewProfileResponse)
async def get_profile(
    user_id: UUID = Depends(get_current_user_auth), db: AsyncSession = Depends(get_db)
):
    return _profile_response(await InterviewService(db).get_or_create_profile(user_id))


@router.put("/profile", response_model=InterviewProfileResponse)
async def update_profile(
    data: InterviewProfileUpdate,
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    return _profile_response(await InterviewService(db).update_profile(user_id, data))


@router.get("/claims", response_model=list[InterviewClaimResponse])
async def list_claims(
    user_id: UUID = Depends(get_current_user_auth), db: AsyncSession = Depends(get_db)
):
    return [_claim_response(item) for item in await InterviewService(db).list_claims(user_id)]


@router.post("/claims", response_model=InterviewClaimResponse)
async def add_claim(
    data: InterviewClaimCreate,
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    return _claim_response(await InterviewService(db).add_claim(user_id, data))


@router.patch("/claims/{claim_id}", response_model=InterviewClaimResponse)
async def update_claim(
    claim_id: UUID,
    data: InterviewClaimUpdate,
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    claim = await InterviewService(db).update_claim(user_id, claim_id, data)
    if claim is None:
        raise HTTPException(status_code=404, detail="Interview claim not found")
    return _claim_response(claim)


@router.post("/review-cards", response_model=ReviewCardResponse)
async def add_review_card(
    data: ReviewCardCreate,
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    return _card_response(await InterviewService(db).add_review_card(user_id, data))


@router.get("/review-cards", response_model=list[ReviewCardResponse])
async def list_review_cards(
    due: bool = Query(default=False),
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    cards = await InterviewService(db).list_review_cards(user_id, due_only=due)
    return [_card_response(card) for card in cards]


@router.patch("/review-cards/{card_id}", response_model=ReviewCardResponse)
async def update_review_card(
    card_id: UUID,
    data: ReviewCardUpdate,
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    card = await InterviewService(db).update_review_card(user_id, card_id, data)
    if card is None:
        raise HTTPException(status_code=404, detail="Review card not found")
    return _card_response(card)


@router.get("/training/next", response_model=TrainingPromptResponse, deprecated=True)
async def next_training_prompt(
    level: str | None = Query(default=None, pattern="^P[567]$"),
    topic: str | None = Query(default=None),
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    return await InterviewService(db).next_training_prompt(user_id, level=level, topic=topic)


@router.post("/training/evaluate", response_model=EvaluateAnswerResponse, deprecated=True)
async def evaluate_training_answer(
    data: EvaluateAnswerRequest,
    _: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    return InterviewService(db).evaluate(data)


@router.post("/training/hint", response_model=HintResponse, deprecated=True)
async def training_hint(
    data: HintRequest,
    _: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    return InterviewService(db).progressive_hint(data)


@router.get("/training/progress", response_model=TrainingProgressResponse)
async def get_training_progress(
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    """P0–P2 training progress: coverage, depth, retention, expectations, score, trend."""
    return await InterviewService(db).get_training_progress(user_id)


@router.get("/training/attempts/active", response_model=ActiveAttemptResponse)
async def get_active_attempt(
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    attempt = await InterviewService(db).get_active_attempt(user_id)
    return ActiveAttemptResponse(attempt=attempt)


@router.post("/training/attempts", response_model=TrainingAttemptResponse)
async def create_training_attempt(
    data: CreateAttemptRequest = Body(default_factory=CreateAttemptRequest),
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    return await InterviewService(db).create_or_resume_attempt(user_id, data)


@router.post("/training/attempts/{attempt_id}/answers", response_model=SubmitAnswerResponse)
async def submit_attempt_answer(
    attempt_id: UUID,
    data: SubmitAnswerRequest,
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    return await InterviewService(db).submit_answer(user_id, attempt_id, data)


@router.post("/training/attempts/{attempt_id}/hints", response_model=HintResponse)
async def attempt_hint(
    attempt_id: UUID,
    data: AttemptHintRequest,
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    return await InterviewService(db).attempt_hint(user_id, attempt_id, data)


@router.post("/training/attempts/{attempt_id}/commit", response_model=TrainingAttemptResponse)
async def commit_attempt(
    attempt_id: UUID,
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    return await InterviewService(db).commit_attempt(user_id, attempt_id)


@router.post("/training/attempts/{attempt_id}/abandon", response_model=TrainingAttemptResponse)
async def abandon_attempt(
    attempt_id: UUID,
    data: AbandonAttemptRequest | None = None,
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    return await InterviewService(db).abandon_attempt(
        user_id, attempt_id, data or AbandonAttemptRequest()
    )
