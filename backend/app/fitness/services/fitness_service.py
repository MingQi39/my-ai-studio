"""Fitness goal and diary services."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.fitness.schemas import DiaryEntryResponse, FitnessGoalResponse, TodaySummaryResponse
from app.fitness.timezone import today_for_timezone
from app.models.database import FitnessDiaryEntry, FitnessGoal, FitnessMealType

DISCLAIMER = (
    "本工具仅用于生活方式记录与热量估算，不能替代医疗或营养诊断建议。"
)


class FitnessService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_goal(self, user_id: UUID) -> FitnessGoalResponse:
        goal = await self._get_goal_row(user_id)
        if not goal:
            return FitnessGoalResponse(
                daily_calorie_goal=settings.FITNESS_DEFAULT_CALORIE_GOAL,
                updated_at=None,
            )
        return FitnessGoalResponse(
            daily_calorie_goal=goal.daily_calorie_goal,
            updated_at=goal.updated_at,
        )

    async def set_goal(self, user_id: UUID, daily_calorie_goal: int) -> FitnessGoalResponse:
        goal = await self._get_goal_row(user_id)
        if goal is None:
            goal = FitnessGoal(
                user_id=str(user_id),
                daily_calorie_goal=daily_calorie_goal,
            )
            self.db.add(goal)
        else:
            goal.daily_calorie_goal = daily_calorie_goal
        await self.db.flush()
        await self.db.refresh(goal)
        return FitnessGoalResponse(
            daily_calorie_goal=goal.daily_calorie_goal,
            updated_at=goal.updated_at,
        )

    async def get_today_summary(
        self,
        user_id: UUID,
        *,
        timezone_name: str | None = None,
        on_date: date | None = None,
    ) -> TodaySummaryResponse:
        target_date = on_date or today_for_timezone(timezone_name)
        goal = await self.get_goal(user_id)
        entries = await self.list_entries(user_id, target_date)
        consumed = round(sum(entry.total_kcal for entry in entries), 1)
        remaining = round(goal.daily_calorie_goal - consumed, 1)
        return TodaySummaryResponse(
            date=target_date,
            daily_calorie_goal=goal.daily_calorie_goal,
            consumed_kcal=consumed,
            remaining_kcal=remaining,
            entries=entries,
            disclaimer=DISCLAIMER,
        )

    async def list_entries(self, user_id: UUID, on_date: date) -> list[DiaryEntryResponse]:
        result = await self.db.execute(
            select(FitnessDiaryEntry)
            .where(
                FitnessDiaryEntry.user_id == str(user_id),
                FitnessDiaryEntry.date == on_date,
            )
            .order_by(FitnessDiaryEntry.created_at.asc())
        )
        rows = result.scalars().all()
        return [self._to_entry_response(row) for row in rows]

    async def log_meal(
        self,
        user_id: UUID,
        *,
        meal_type: FitnessMealType | str,
        items: list[dict[str, Any]],
        on_date: date | None = None,
        note: str | None = None,
        session_id: UUID | str | None = None,
        timezone_name: str | None = None,
    ) -> DiaryEntryResponse:
        target_date = on_date or today_for_timezone(timezone_name)
        meal = meal_type if isinstance(meal_type, FitnessMealType) else FitnessMealType(meal_type)
        total_kcal = round(sum(float(item.get("kcal", 0) or 0) for item in items), 1)
        entry = FitnessDiaryEntry(
            user_id=str(user_id),
            date=target_date,
            meal_type=meal,
            items=items,
            total_kcal=total_kcal,
            note=note,
            session_id=str(session_id) if session_id else None,
        )
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)
        return self._to_entry_response(entry)

    async def delete_entry(self, user_id: UUID, entry_id: UUID | str) -> bool:
        result = await self.db.execute(
            select(FitnessDiaryEntry).where(
                FitnessDiaryEntry.id == str(entry_id),
                FitnessDiaryEntry.user_id == str(user_id),
            )
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            return False
        await self.db.delete(entry)
        await self.db.flush()
        return True

    async def _get_goal_row(self, user_id: UUID) -> FitnessGoal | None:
        result = await self.db.execute(
            select(FitnessGoal).where(FitnessGoal.user_id == str(user_id))
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _to_entry_response(entry: FitnessDiaryEntry) -> DiaryEntryResponse:
        return DiaryEntryResponse(
            id=entry.id,
            date=entry.date,
            meal_type=entry.meal_type,
            items=entry.items or [],
            total_kcal=entry.total_kcal,
            note=entry.note,
            session_id=entry.session_id,
            created_at=entry.created_at,
        )
