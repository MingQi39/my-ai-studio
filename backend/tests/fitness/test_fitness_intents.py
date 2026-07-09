from app.fitness.services.fitness_intents import (
    detect_meal_type,
    extract_goal_kcal,
    is_goal_update_request,
    is_low_signal_message,
    is_meal_log_request,
    is_recommendation_request,
)


def test_extract_goal_kcal_from_set_phrase():
    assert extract_goal_kcal("把我的每日热量目标设为 1600 kcal") == 1600


def test_extract_goal_kcal_from_compact_phrase():
    assert extract_goal_kcal("目标改成1800大卡") == 1800


def test_is_goal_update_request():
    assert is_goal_update_request("把我的每日热量目标设为 1600 kcal") is True
    assert is_goal_update_request("今天天气不错") is False


def test_recommendation_intent():
    assert is_recommendation_request("晚饭不知道吃什么，剩余约 1800 kcal，请推荐 2-3 套") is True
    assert detect_meal_type("晚饭不知道吃什么") == "dinner"


def test_meal_log_intent():
    assert is_meal_log_request("中午吃了一个香蕉，一个芒果班戟山姆的") is True
    assert is_meal_log_request("我想记录午饭，吃了：米饭一碗、番茄炒蛋") is True
    assert is_meal_log_request("今天还剩多少 kcal") is False
    assert is_meal_log_request("晚饭不知道吃什么") is False


def test_low_signal_message_detection():
    assert is_low_signal_message("g") is True
    assert is_low_signal_message("ok") is True
    assert is_low_signal_message("嗯") is True
    assert is_low_signal_message("晚餐吃了牛排 100克") is False
