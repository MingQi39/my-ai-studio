from app.fitness.services.meal_parser import extract_foods_heuristic, parse_meal_foods_from_message
from app.fitness.services.fitness_intents import is_meal_log_request


def test_meal_log_intent_snack():
    assert is_meal_log_request("吃了一个牛肉筋小包装") is True
    assert is_meal_log_request("中午吃了一个香蕉，一个芒果班戟山姆的") is True


def test_extract_foods_heuristic_banana_pancake():
    foods = extract_foods_heuristic("中午吃了一个香蕉，一个芒果班戟山姆的")
    assert len(foods) == 2
    assert foods[0].name == "香蕉"
    assert foods[0].qty == 1
    assert foods[1].name == "山姆芒果班戟"


def test_extract_foods_heuristic_guided_template():
    foods = extract_foods_heuristic("我想记录午饭，吃了：牛肉筋小包装")
    assert len(foods) == 1
    assert "牛肉筋" in foods[0].name


def test_extract_foods_heuristic_beef_tendon():
    foods = extract_foods_heuristic("吃了一个牛肉筋小包装")
    assert len(foods) == 1
    assert "牛肉筋" in foods[0].name


def test_extract_foods_heuristic_gram_suffix():
    foods = extract_foods_heuristic("晚上还想吃上脑皇250g")
    assert len(foods) == 1
    assert foods[0].name == "上脑皇"
    assert foods[0].qty == 250
    assert foods[0].unit == "克"
