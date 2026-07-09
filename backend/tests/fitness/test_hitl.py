from app.fitness.services.hitl import (
    build_approval_preview,
    build_approval_prompt,
    build_approval_success_message,
    execute_write_tool,
    is_write_tool,
)


def test_is_write_tool():
    assert is_write_tool("log_meal") is True
    assert is_write_tool("get_today_summary") is False


def test_build_approval_preview_set_goal():
    preview = build_approval_preview(
        "set_daily_calorie_goal",
        {"daily_calorie_goal": 1600},
        previous_goal=1800,
    )
    assert preview["kind"] == "set_goal"
    assert preview["daily_calorie_goal"] == 1600
    assert preview["previous_daily_calorie_goal"] == 1800


def test_build_approval_preview_log_meal():
    preview = build_approval_preview(
        "log_meal",
        {
            "meal_type": "lunch",
            "items": [{"name": "米饭", "kcal": 200}, {"name": "番茄炒蛋", "kcal": 180}],
        },
    )
    assert preview["kind"] == "log_meal"
    assert preview["total_kcal"] == 380


def test_build_approval_prompt_set_goal():
    prompt = build_approval_prompt(
        "set_daily_calorie_goal",
        {
            "kind": "set_goal",
            "daily_calorie_goal": 1600,
            "previous_daily_calorie_goal": 1800,
        },
    )
    assert "1600" in prompt
    assert "1800" in prompt


def test_build_approval_success_message_log_meal():
    message = build_approval_success_message(
        "log_meal",
        {"meal_type": "lunch", "total_kcal": 380},
    )
    assert "午餐" in message
    assert "380" in message
