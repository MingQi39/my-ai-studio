"""Structured travel plan models for formal itinerary export."""

from __future__ import annotations

from pydantic import BaseModel, Field
from uuid import UUID


class PlanLocation(BaseModel):
    name: str
    address: str | None = None
    note: str | None = None


class PlanActivity(BaseModel):
    time: str | None = None
    title: str
    description: str | None = None
    location: PlanLocation | None = None


class PlanDay(BaseModel):
    day: int = Field(ge=1)
    title: str | None = None
    activities: list[PlanActivity] = Field(default_factory=list)


class PlanBudgetItem(BaseModel):
    category: str
    amount: float | None = None
    currency: str = "CNY"
    note: str | None = None


class StructuredTravelPlan(BaseModel):
    title: str
    destination: str
    duration_days: int | None = None
    travel_dates: str | None = None
    budget_total: float | None = None
    budget_currency: str = "CNY"
    summary: str
    weather_summary: str | None = None
    daily_itinerary: list[PlanDay] = Field(default_factory=list)
    accommodations: list[PlanLocation] = Field(default_factory=list)
    transport: list[str] = Field(default_factory=list)
    budget_breakdown: list[PlanBudgetItem] = Field(default_factory=list)
    tips: list[str] = Field(default_factory=list)
    data_verified: bool = False


class ToolEvidenceItem(BaseModel):
    tool_name: str
    result: str


class TravelPlanGenerateRequest(BaseModel):
    model_config_id: UUID
    session_id: UUID | None = None
    user_request: str | None = None
    assistant_plan: str | None = None
    tool_evidence: list[ToolEvidenceItem] = Field(default_factory=list)
    data_verified: bool = False


class TravelPlanGenerateResponse(BaseModel):
    plan: StructuredTravelPlan
    markdown: str
    fingerprint: str | None = None
    exists: bool = True
    is_stale: bool = False
    generated_at: str | None = None


class TravelPlanStatusResponse(BaseModel):
    exists: bool
    is_stale: bool = False
    fingerprint: str | None = None
    generated_at: str | None = None
    plan: StructuredTravelPlan | None = None
    markdown: str | None = None
