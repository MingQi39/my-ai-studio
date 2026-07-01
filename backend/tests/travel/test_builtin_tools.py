import json
from unittest.mock import AsyncMock, patch

import pytest

from app.travel.tools import builtin


@pytest.mark.asyncio
async def test_get_weather_requires_amap_key():
    with patch("app.travel.tools.builtin.get_settings") as mock_settings:
        mock_settings.return_value.amap_api_key = ""
        result = json.loads(await builtin.get_weather_handler("北京"))
        assert "error" in result
        assert "AMAP_API_KEY" in result["error"]


@pytest.mark.asyncio
async def test_get_weather_returns_amap_data():
    with patch("app.travel.tools.builtin.get_settings") as mock_settings:
        mock_settings.return_value.amap_api_key = "test-key"
        mock_settings.return_value.http_timeout_seconds = 10
        with patch("app.travel.tools.builtin.AMapClient") as mock_client_cls:
            mock_client = mock_client_cls.return_value
            mock_client.get_weather = AsyncMock(return_value={
                "city": "北京市",
                "date": "今天",
                "temperature": "28",
                "weather": "晴",
                "humidity": "40",
                "wind_direction": "南",
                "wind_power": "≤3",
            })
            result = json.loads(await builtin.get_weather_handler("北京"))
            assert result["source"] == "amap"
            assert result["city"] == "北京市"
            assert result["suitable_for_travel"] is True


@pytest.mark.asyncio
async def test_search_transport_uses_juhe_structured_data():
    with patch("app.travel.tools.builtin.get_settings") as mock_settings:
        mock_settings.return_value.amap_api_key = ""
        mock_settings.return_value.tavily_api_key = ""
        mock_settings.return_value.juhe_train_api_key = "juhe-train"
        mock_settings.return_value.juhe_flight_api_key = "juhe-flight"
        mock_settings.return_value.http_timeout_seconds = 10
        with patch("app.travel.tools.builtin.JuheClient") as mock_juhe_cls:
            mock_juhe = mock_juhe_cls.return_value
            mock_juhe.query_trains = AsyncMock(return_value=[{
                "mode": "train",
                "train_no": "G1",
                "source": "juhe",
            }])
            mock_juhe.query_flights = AsyncMock(return_value=[{
                "mode": "flight",
                "flight_no": "CA1234",
                "source": "juhe",
            }])
            result = json.loads(await builtin.search_transport_handler("北京", "上海", "2026-07-01"))
            assert len(result["options"]) == 2
            assert result["options"][0]["mode"] == "train"
            assert result["options"][1]["mode"] == "flight"
            assert result["date"] == "2026-07-01"


@pytest.mark.asyncio
async def test_search_transport_falls_back_to_tavily_without_juhe():
    with patch("app.travel.tools.builtin.get_settings") as mock_settings:
        mock_settings.return_value.amap_api_key = ""
        mock_settings.return_value.juhe_train_api_key = ""
        mock_settings.return_value.juhe_flight_api_key = ""
        mock_settings.return_value.tavily_api_key = "tvly-test"
        mock_settings.return_value.http_timeout_seconds = 10
        mock_settings.return_value.tavily_max_results = 3
        with patch("app.travel.tools.builtin.TavilyClient") as mock_tavily_cls:
            mock_tavily = mock_tavily_cls.return_value
            mock_tavily.search = AsyncMock(return_value=[{
                "title": "北京到上海高铁",
                "content": "G1 4小时30分 553元",
                "url": "https://example.com",
                "score": 0.9,
            }])
            result = json.loads(await builtin.search_transport_handler("北京", "上海"))
            assert len(result["options"]) == 1
            assert result["options"][0]["source"] == "tavily"


@pytest.mark.asyncio
async def test_search_food_recommendations_requires_tavily_key():
    with patch("app.travel.tools.builtin.get_settings") as mock_settings:
        mock_settings.return_value.tavily_api_key = ""
        result = json.loads(await builtin.search_food_recommendations_handler("成都"))
        assert "error" in result
        assert "TAVILY_API_KEY" in result["error"]


@pytest.mark.asyncio
async def test_search_food_recommendations_returns_tavily_results():
    with patch("app.travel.tools.builtin.get_settings") as mock_settings:
        mock_settings.return_value.tavily_api_key = "tvly-test"
        mock_settings.return_value.http_timeout_seconds = 10
        mock_settings.return_value.tavily_max_results = 3
        with patch("app.travel.tools.builtin.TavilyClient") as mock_tavily_cls:
            mock_tavily = mock_tavily_cls.return_value
            mock_tavily.search = AsyncMock(return_value=[{
                "title": "成都春熙路美食攻略 小红书",
                "content": "必吃钵钵鸡、龙抄手，避雷某网红店",
                "url": "https://example.com/xhs-food",
                "score": 0.88,
            }])
            result = json.loads(
                await builtin.search_food_recommendations_handler("成都", area="春熙路", cuisine="小吃")
            )
            assert result["source"] == "tavily"
            assert result["count"] == 1
            assert "小红书" in result["query"]
            assert result["recommendations"][0]["title"] == "成都春熙路美食攻略 小红书"
            mock_tavily.search.assert_awaited_once_with("成都 春熙路 小吃 美食 推荐 小红书")
