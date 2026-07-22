"""Model purpose routing for interview agent (eval vs hint vs reflect)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.config import settings

InterviewModelPurpose = Literal["evaluate", "hint", "reflect", "embed"]


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
            provider_hint=getattr(settings, "INTERVIEW_HINT_PROVIDER", "rules"),
            model_id=getattr(settings, "INTERVIEW_HINT_MODEL", "rules"),
            temperature=0.0,
        )
    # evaluate: keyword rules by default; optional small model later
    return ModelRoleConfig(
        purpose=purpose,
        provider_hint=getattr(settings, "INTERVIEW_EVAL_PROVIDER", "rules"),
        model_id=getattr(settings, "INTERVIEW_EVAL_MODEL", "rules"),
        temperature=0.0,
    )
