"""Pydantic schemas for the Fitness Agent."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.database import FitnessMealType


CalorieSource = Literal["local", "usda", "web", "estimate"]
Preference = Literal["low_oil", "vegetarian", "cheap", "convenient"]


class FoodItemInput(BaseModel):
    name: str
    qty: float = 1.0
    unit: str = "份"


class ResolvedFoodItem(BaseModel):
    name: str
    qty: float
    unit: str
    kcal: float
    source: CalorieSource
    assumed: bool = False
    note: str | None = None


class FitnessGoalResponse(BaseModel):
    daily_calorie_goal: int
    updated_at: datetime | None = None


class FitnessGoalUpdate(BaseModel):
    daily_calorie_goal: int = Field(ge=800, le=10000)


class DiaryEntryResponse(BaseModel):
    id: str
    date: date
    meal_type: FitnessMealType
    items: list[dict[str, Any]]
    total_kcal: float
    note: str | None = None
    session_id: str | None = None
    created_at: datetime


class TodaySummaryResponse(BaseModel):
    date: date
    daily_calorie_goal: int
    consumed_kcal: float
    remaining_kcal: float
    entries: list[DiaryEntryResponse]
    disclaimer: str


class MealRecommendationItem(BaseModel):
    name: str
    qty: float
    unit: str
    kcal: float
    source: CalorieSource


class MealRecommendation(BaseModel):
    id: str
    title: str
    items: list[MealRecommendationItem]
    total_kcal: float
    preference_fit: list[str] = Field(default_factory=list)
    notes: str | None = None


class FitnessAgentRequest(BaseModel):
    message: str
    session_id: UUID | None = None
    model_config_id: UUID
    timezone: str | None = None
    max_rounds: int | None = 3


class FitnessAgentApproveRequest(BaseModel):
    session_id: UUID | None = None
    tool_name: str
    tool_args: dict[str, Any] = Field(default_factory=dict)
    call_id: str | None = None
    timezone: str | None = None


class FitnessAgentApproveResponse(BaseModel):
    ok: bool
    tool_name: str
    result: dict[str, Any] | None = None
    message: str
