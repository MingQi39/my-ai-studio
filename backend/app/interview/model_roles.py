"""Model purpose routing for interview agent (eval vs hint vs reflect)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.config import settings

InterviewModelPurpose = Literal["evaluate", "hint", "reflect", "embed", "resume_craft", "daily_doc"]


@dataclass(frozen=True)
class ModelRoleConfig:
    purpose: InterviewModelPurpose
    provider_hint: str
    model_id: str
    temperature: float


def resolve_model_role(purpose: InterviewModelPurpose) -> ModelRoleConfig:
    """Map purpose → configured model. Defaults keep eval/hint local & cheap."""
    if purpose == "embed":
        return ModelRoleConfig(
            purpose=purpose,
            provider_hint="ollama",
            model_id=settings.INTERVIEW_EMBEDDING_MODEL,
            temperature=0.0,
        )
    if purpose == "reflect":
        return ModelRoleConfig(
            purpose=purpose,
            provider_hint=getattr(settings, "INTERVIEW_REFLECT_PROVIDER", "openai_compatible"),
            model_id=getattr(settings, "INTERVIEW_REFLECT_MODEL", "gpt-4o-mini"),
            temperature=0.1,
        )
    if purpose == "hint":
        return ModelRoleConfig(
            purpose=purpose,
            provider_hint=getattr(settings, "INTERVIEW_HINT_PROVIDER", "openai_compatible"),
            model_id=getattr(settings, "INTERVIEW_HINT_MODEL", "gpt-4o-mini"),
            temperature=0.2,
        )
    if purpose == "resume_craft":
        return ModelRoleConfig(
            purpose=purpose,
            provider_hint=getattr(settings, "INTERVIEW_RESUME_CRAFT_PROVIDER", "template"),
            model_id=getattr(settings, "INTERVIEW_RESUME_CRAFT_MODEL", "template"),
            temperature=0.3,
        )
    if purpose == "daily_doc":
        # Prefer dedicated daily_doc settings; otherwise inherit HINT so BYOK
        # DeepSeek/OpenAI configs stay consistent (model must match the base URL).
        provider = (
            (getattr(settings, "INTERVIEW_DAILY_DOC_PROVIDER", "") or "").strip()
            or getattr(settings, "INTERVIEW_HINT_PROVIDER", "openai_compatible")
            or "openai_compatible"
        )
        model_id = (
            (getattr(settings, "INTERVIEW_DAILY_DOC_MODEL", "") or "").strip()
            or getattr(settings, "INTERVIEW_HINT_MODEL", "")
            or "gpt-4o-mini"
        )
        return ModelRoleConfig(
            purpose=purpose,
            provider_hint=provider,
            model_id=model_id,
            temperature=0.35,
        )
    # evaluate: keyword rules by default; optional small model later
    return ModelRoleConfig(
        purpose=purpose,
        provider_hint=getattr(settings, "INTERVIEW_EVAL_PROVIDER", "rules"),
        model_id=getattr(settings, "INTERVIEW_EVAL_MODEL", "rules"),
        temperature=0.0,
    )
