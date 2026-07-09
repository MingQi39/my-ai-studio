import pytest
from unittest.mock import AsyncMock, patch

from app.fitness.schemas import FoodItemInput, ResolvedFoodItem
from app.fitness.services.calorie_resolver import resolve_food_calories


@pytest.mark.asyncio
async def test_resolve_food_calories_local_hit():
    # local db includes "白米饭"
    foods = [FoodItemInput(name="白米饭", qty=1, unit="碗")]

    # LLM client should not be called for local hit
    openai_client = AsyncMock()
    resolved = await resolve_food_calories(
        foods,
        openai_client=openai_client,
        model_name="test-model",
        usda_api_key=None,
        tavily_api_key="",
    )

    assert len(resolved) == 1
    assert resolved[0].name == "白米饭"
    assert resolved[0].source == "local"
    assert resolved[0].assumed is False


@pytest.mark.asyncio
async def test_resolve_food_calories_llm_estimate_fallback_when_unknown():
    foods = [FoodItemInput(name="不存在的食物XYZ", qty=2, unit="份")]

    # Mock openai estimate response
    openai_client = AsyncMock()
    openai_client.chat.completions.create = AsyncMock(
        return_value=type(
            "Resp",
            (),
            {
                "choices": [
                    type(
                        "Choice",
                        (),
                        {
                            "message": type(
                                "Msg",
                                (),
                                {"content": '{"kcal": 300, "assumed": true}'},
                            )(),
                        },
                    )()
                ]
            },
        )()
    )

    with patch(
        "app.fitness.services.calorie_resolver._resolve_calories_web_search",
        new=AsyncMock(return_value=None),
    ):
        resolved = await resolve_food_calories(
            foods,
            openai_client=openai_client,
            model_name="test-model",
            usda_api_key=None,
            tavily_api_key="dummy-key",
        )

    assert len(resolved) == 1
    assert resolved[0].source == "estimate"
    assert resolved[0].kcal == 300
    assert resolved[0].assumed is True


@pytest.mark.asyncio
async def test_fallback_estimate_kcal_gram_unit_not_multiplied_raw():
    """250g meat must not become 150 * 250 = 37500 kcal."""
    from app.fitness.services.calorie_resolver import _fallback_estimate_kcal

    assert _fallback_estimate_kcal("上脑皇", 250, "克") == 625.0
    assert _fallback_estimate_kcal("烤排骨", 100, "克") == 250.0


@pytest.mark.asyncio
async def test_resolve_food_calories_llm_insane_kcal_gets_corrected():
    foods = [FoodItemInput(name="上脑皇", qty=250, unit="克")]

    openai_client = AsyncMock()
    openai_client.chat.completions.create = AsyncMock(
        return_value=type(
            "Resp",
            (),
            {
                "choices": [
                    type(
                        "Choice",
                        (),
                        {
                            "message": type(
                                "Msg",
                                (),
                                {"content": '{"kcal": 37500, "assumed": true}'},
                            )(),
                        },
                    )()
                ]
            },
        )()
    )

    with patch(
        "app.fitness.services.calorie_resolver._resolve_calories_web_search",
        new=AsyncMock(return_value=None),
    ):
        resolved = await resolve_food_calories(
            foods,
            openai_client=openai_client,
            model_name="test-model",
            usda_api_key=None,
            tavily_api_key="dummy-key",
        )

    assert len(resolved) == 1
    assert resolved[0].kcal == 625.0
    assert resolved[0].source == "estimate"
    assert "修正" in (resolved[0].note or "")


@pytest.mark.asyncio
async def test_resolve_food_calories_llm_insane_kcal_prefers_llm_reestimate():
    foods = [FoodItemInput(name="上脑皇", qty=250, unit="克")]

    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        # First call: bad estimate; second call: semantic re-estimate
        kcal = 37500 if call_count == 1 else 580
        return type(
            "Resp",
            (),
            {
                "choices": [
                    type(
                        "Choice",
                        (),
                        {
                            "message": type(
                                "Msg",
                                (),
                                {"content": f'{{"kcal": {kcal}, "assumed": true}}'},
                            )(),
                        },
                    )()
                ]
            },
        )()

    openai_client = AsyncMock()
    openai_client.chat.completions.create = mock_create

    with patch(
        "app.fitness.services.calorie_resolver._resolve_calories_web_search",
        new=AsyncMock(return_value=None),
    ):
        resolved = await resolve_food_calories(
            foods,
            openai_client=openai_client,
            model_name="test-model",
            usda_api_key=None,
            tavily_api_key="dummy-key",
        )

    assert len(resolved) == 1
    assert resolved[0].kcal == 580
    assert "LLM 重新估算" in (resolved[0].note or "")
    assert call_count >= 2


@pytest.mark.asyncio
async def test_resolve_food_calories_local_hit_mango_pancake_alias():
    foods = [FoodItemInput(name="芒果班戟山姆的", qty=1, unit="个")]

    openai_client = AsyncMock()
    resolved = await resolve_food_calories(
        foods,
        openai_client=openai_client,
        model_name="test-model",
        usda_api_key=None,
        tavily_api_key="",
    )

    assert len(resolved) == 1
    assert resolved[0].name == "山姆芒果班戟"
    assert resolved[0].source == "local"
    assert resolved[0].kcal == 220
    openai_client.chat.completions.create.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_food_calories_llm_zero_kcal_uses_fallback():
    foods = [FoodItemInput(name="神秘外星食物", qty=1, unit="份")]

    openai_client = AsyncMock()
    openai_client.chat.completions.create = AsyncMock(
        return_value=type(
            "Resp",
            (),
            {
                "choices": [
                    type(
                        "Choice",
                        (),
                        {
                            "message": type(
                                "Msg",
                                (),
                                {"content": '{"kcal": 0, "assumed": true}'},
                            )(),
                        },
                    )()
                ]
            },
        )()
    )

    with patch(
        "app.fitness.services.calorie_resolver._resolve_calories_web_search",
        new=AsyncMock(return_value=None),
    ):
        resolved = await resolve_food_calories(
            foods,
            openai_client=openai_client,
            model_name="test-model",
            usda_api_key=None,
            tavily_api_key="dummy-key",
        )

    assert len(resolved) == 1
    assert resolved[0].source == "estimate"
    assert resolved[0].kcal > 0
    assert "兜底" in (resolved[0].note or "")


@pytest.mark.asyncio
async def test_resolve_food_calories_web_search_hit():
    foods = [FoodItemInput(name="某品牌能量棒", qty=1, unit="根")]

    openai_client = AsyncMock()
    web_item = ResolvedFoodItem(
        name="某品牌能量棒",
        qty=1,
        unit="根",
        kcal=210,
        source="web",
        assumed=True,
        note="联网搜索参考（仅供参考）",
    )

    with patch(
        "app.fitness.services.calorie_resolver._resolve_calories_web_search",
        new=AsyncMock(return_value=web_item),
    ):
        resolved = await resolve_food_calories(
            foods,
            openai_client=openai_client,
            model_name="test-model",
            usda_api_key=None,
            tavily_api_key="dummy-key",
        )

    assert len(resolved) == 1
    assert resolved[0].source == "web"
    assert resolved[0].kcal == 210
    openai_client.chat.completions.create.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_food_calories_usda_validated_and_corrected():
    foods = [FoodItemInput(name="上脑皇", qty=250, unit="克")]

    openai_client = AsyncMock()
    openai_client.chat.completions.create = AsyncMock(
        return_value=type(
            "Resp",
            (),
            {
                "choices": [
                    type(
                        "Choice",
                        (),
                        {
                            "message": type(
                                "Msg",
                                (),
                                {
                                    "content": (
                                        '{"plausible": false, "kcal": 85, '
                                        '"reason": "USDA 匹配条目与上脑皇不符"}'
                                    )
                                },
                            )(),
                        },
                    )()
                ]
            },
        )()
    )

    usda_resolved = type("USDAResolved", (), {"kcal_per_base_qty": 1.0, "base_qty": 1.0})()

    with patch(
        "app.fitness.services.calorie_resolver._resolve_usda_energy_kcal_per_serving",
        new=AsyncMock(return_value=usda_resolved),
    ), patch(
        "app.fitness.services.calorie_resolver._resolve_calories_web_search",
        new=AsyncMock(return_value=None),
    ):
        resolved = await resolve_food_calories(
            foods,
            openai_client=openai_client,
            model_name="test-model",
            usda_api_key="dummy-key",
            tavily_api_key="dummy-key",
        )

    assert len(resolved) == 1
    assert resolved[0].kcal == 85
    assert resolved[0].source == "estimate"
    assert "校验修正" in (resolved[0].note or "")
    openai_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_resolve_food_calories_local_suspicious_kcal_gets_validated():
    foods = [FoodItemInput(name="神秘肉", qty=250, unit="克")]

    openai_client = AsyncMock()
    openai_client.chat.completions.create = AsyncMock(
        return_value=type(
            "Resp",
            (),
            {
                "choices": [
                    type(
                        "Choice",
                        (),
                        {
                            "message": type(
                                "Msg",
                                (),
                                {
                                    "content": (
                                        '{"plausible": false, "kcal": 420, '
                                        '"reason": "每克热量过低"}'
                                    )
                                },
                            )(),
                        },
                    )()
                ]
            },
        )()
    )

    local_entry = type(
        "LocalFoodEntry",
        (),
        {"name": "神秘肉", "unit": "克", "kcal": 1.0, "qty": 250.0, "grams": 250.0, "aliases": []},
    )()

    with patch(
        "app.fitness.services.calorie_resolver.resolve_local_food",
        return_value=local_entry,
    ), patch(
        "app.fitness.services.calorie_resolver.is_exact_local_match",
        return_value=False,
    ), patch(
        "app.fitness.services.calorie_resolver._resolve_calories_web_search",
        new=AsyncMock(return_value=None),
    ):
        resolved = await resolve_food_calories(
            foods,
            openai_client=openai_client,
            model_name="test-model",
            usda_api_key=None,
            tavily_api_key="dummy-key",
        )

    assert len(resolved) == 1
    assert resolved[0].kcal == 420
    assert resolved[0].source == "estimate"
    openai_client.chat.completions.create.assert_called_once()
