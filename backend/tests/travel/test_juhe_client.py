import pytest

from app.travel.services.exceptions import ExternalAPIError
from app.travel.services.juhe_client import JuheClient, normalize_city, resolve_city_iata


def test_normalize_city():
    assert normalize_city("北京市") == "北京"
    assert normalize_city("上海") == "上海"


def test_resolve_city_iata():
    assert resolve_city_iata("北京") == "BJS"
    assert resolve_city_iata("SHA") == "SHA"


def test_resolve_city_iata_unknown():
    with pytest.raises(ExternalAPIError):
        resolve_city_iata("NotARealCityXYZ")


@pytest.mark.asyncio
async def test_query_trains_parses_result(monkeypatch):
    client = JuheClient(train_api_key="test-key", flight_api_key="test-key")

    async def fake_request(url, params, api_key):
        assert "train" in url
        return [
            {
                "train_no": "G1",
                "departure_station": "北京南",
                "arrival_station": "上海虹桥",
                "departure_time": "09:00",
                "arrival_time": "13:28",
                "duration": "04:28",
                "enable_booking": "Y",
                "prices": [{"seat_type": "二等座", "price": 553}],
                "train_flags": ["复兴号"],
            }
        ]

    monkeypatch.setattr(client, "_request", fake_request)
    trains = await client.query_trains("北京", "上海", "2026-07-01")
    assert trains[0]["mode"] == "train"
    assert trains[0]["train_no"] == "G1"
    assert trains[0]["min_price"] == 553


@pytest.mark.asyncio
async def test_query_flights_parses_result(monkeypatch):
    client = JuheClient(train_api_key="test-key", flight_api_key="test-key")

    async def fake_request(url, params, api_key):
        assert "flight" in url
        return {
            "flightInfo": [
                {
                    "airline": "CA",
                    "airlineName": "中国国际航空",
                    "flightNo": "CA1234",
                    "departureName": "首都国际机场",
                    "arrivalName": "虹桥国际机场",
                    "departureDate": "2026-07-01",
                    "departureTime": "08:00",
                    "arrivalDate": "2026-07-01",
                    "arrivalTime": "10:10",
                    "duration": "02:10",
                    "ticketPrice": 980,
                    "transferNum": 0,
                }
            ]
        }

    monkeypatch.setattr(client, "_request", fake_request)
    flights = await client.query_flights("北京", "上海", "2026-07-01")
    assert flights[0]["mode"] == "flight"
    assert flights[0]["flight_no"] == "CA1234"
    assert flights[0]["ticket_price"] == 980
