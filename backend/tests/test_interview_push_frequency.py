"""Tests for push frequency scheduling."""

from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.interview.plan_service import is_push_due, should_push_on_date


def test_should_push_on_weekdays():
    monday = date(2026, 7, 20)  # Monday
    saturday = date(2026, 7, 25)  # Saturday
    assert should_push_on_date("weekdays", monday) is True
    assert should_push_on_date("weekdays", saturday) is False
    assert should_push_on_date("daily", saturday) is True
    assert should_push_on_date("weekends", saturday) is True
    assert should_push_on_date("weekends", monday) is False


def test_is_push_due_respects_weekday_frequency():
    profile = SimpleNamespace(
        push_enabled=True,
        target_deadline=date(2026, 12, 1),
        push_timezone="Asia/Shanghai",
        push_time="21:00",
        push_frequency="weekdays",
        last_push_date=None,
    )
    weekday_due = datetime(2026, 7, 22, 21, 0, tzinfo=ZoneInfo("Asia/Shanghai"))  # Wednesday
    weekend_not_due = datetime(2026, 7, 25, 21, 0, tzinfo=ZoneInfo("Asia/Shanghai"))  # Saturday
    assert is_push_due(profile, now=weekday_due) is True
    assert is_push_due(profile, now=weekend_not_due) is False


def test_push_time_normalizes_seconds():
    from app.interview.schemas import PushSettingsUpdate

    data = PushSettingsUpdate(push_time="09:30:00")
    assert data.push_time == "09:30"
    data2 = PushSettingsUpdate(push_time="9:05")
    assert data2.push_time == "09:05"
