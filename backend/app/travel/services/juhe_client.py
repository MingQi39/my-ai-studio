"""
聚合数据 API 客户端 — 火车票 / 航班结构化查询
文档：https://www.juhe.cn/docs/api/id/817 （火车）
      https://www.juhe.cn/docs/api/id/818 （航班）
"""
from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from app.travel.services.exceptions import ExternalAPIError, ExternalAPITimeout

# 常用城市 → 航班城市码（IATA 城市码）
CITY_IATA_MAP: dict[str, str] = {
    "北京": "BJS",
    "上海": "SHA",
    "广州": "CAN",
    "深圳": "SZX",
    "成都": "CTU",
    "杭州": "HGH",
    "南京": "NKG",
    "武汉": "WUH",
    "西安": "SIA",
    "重庆": "CKG",
    "天津": "TSN",
    "青岛": "TAO",
    "大连": "DLC",
    "厦门": "XMN",
    "昆明": "KMG",
    "长沙": "CSX",
    "郑州": "CGO",
    "沈阳": "SHE",
    "哈尔滨": "HRB",
    "海口": "HAK",
    "三亚": "SYX",
    "拉萨": "LXA",
    "乌鲁木齐": "URC",
    "济南": "TNA",
    "福州": "FOC",
    "合肥": "HFE",
    "南昌": "KHN",
    "贵阳": "KWE",
    "南宁": "NNG",
    "石家庄": "SJW",
    "太原": "TYN",
    "兰州": "LHW",
    "银川": "INC",
    "呼和浩特": "HET",
    "宁波": "NGB",
    "无锡": "WUX",
    "珠海": "ZUH",
    "温州": "WNZ",
}


def normalize_city(city: str) -> str:
    city = (city or "").strip()
    if city.endswith("市"):
        return city[:-1]
    return city


def resolve_city_iata(city: str) -> str:
    normalized = normalize_city(city)
    if normalized in CITY_IATA_MAP:
        return CITY_IATA_MAP[normalized]
    upper = normalized.upper()
    if len(upper) == 3 and upper.isalpha():
        return upper
    raise ExternalAPIError(f"暂不支持城市「{city}」的航班查询，请使用三字码或常见城市名")


def default_travel_date(travel_date: str | None) -> str:
    if travel_date:
        return travel_date
    return date.today().strftime("%Y-%m-%d")


class JuheClient:
    TRAIN_URL = "https://apis.juhe.cn/fapigw/train/query"
    FLIGHT_URL = "https://apis.juhe.cn/flight/query"

    def __init__(
        self,
        *,
        train_api_key: str = "",
        flight_api_key: str = "",
        timeout: int = 15,
    ):
        self.train_api_key = train_api_key
        self.flight_api_key = flight_api_key
        self.timeout = timeout

    async def _request(self, url: str, params: dict[str, Any], api_key: str) -> Any:
        if not api_key:
            raise ExternalAPIError("未配置聚合数据 API Key")

        query = {"key": api_key, **params}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=query)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise ExternalAPITimeout("聚合数据 API 请求超时") from exc
        except httpx.HTTPError as exc:
            raise ExternalAPIError(f"聚合数据 API 请求失败: {exc}") from exc

        error_code = data.get("error_code")
        if error_code not in (0, "0", None):
            raise ExternalAPIError(data.get("reason") or f"聚合数据返回错误码 {error_code}")

        return data.get("result")

    def _normalize_train(self, item: dict[str, Any]) -> dict[str, Any]:
        prices = item.get("prices") or []
        min_price = None
        for price_item in prices:
            if not isinstance(price_item, dict):
                continue
            value = price_item.get("price")
            if isinstance(value, (int, float)):
                min_price = value if min_price is None else min(min_price, value)

        return {
            "mode": "train",
            "train_no": item.get("train_no"),
            "departure_station": item.get("departure_station"),
            "arrival_station": item.get("arrival_station"),
            "departure_time": item.get("departure_time"),
            "arrival_time": item.get("arrival_time"),
            "duration": item.get("duration"),
            "enable_booking": item.get("enable_booking"),
            "min_price": min_price,
            "prices": prices,
            "train_flags": item.get("train_flags") or [],
            "source": "juhe",
        }

    def _normalize_flight(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "mode": "flight",
            "airline": item.get("airline"),
            "airline_name": item.get("airlineName"),
            "flight_no": item.get("flightNo"),
            "departure_airport": item.get("departureName") or item.get("departure"),
            "arrival_airport": item.get("arrivalName") or item.get("arrival"),
            "departure_date": item.get("departureDate"),
            "departure_time": item.get("departureTime"),
            "arrival_date": item.get("arrivalDate"),
            "arrival_time": item.get("arrivalTime"),
            "duration": item.get("duration"),
            "ticket_price": item.get("ticketPrice"),
            "transfer_num": item.get("transferNum", 0),
            "equipment": item.get("equipment"),
            "source": "juhe",
        }

    async def query_trains(
        self,
        from_city: str,
        to_city: str,
        travel_date: str | None = None,
        *,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        result = await self._request(
            self.TRAIN_URL,
            {
                "search_type": "1",
                "departure_station": normalize_city(from_city),
                "arrival_station": normalize_city(to_city),
                "date": default_travel_date(travel_date),
                "enable_booking": "2",
            },
            self.train_api_key,
        )

        if not isinstance(result, list):
            return []

        trains = [self._normalize_train(item) for item in result if isinstance(item, dict)]
        return trains[:limit]

    async def query_flights(
        self,
        from_city: str,
        to_city: str,
        travel_date: str | None = None,
        *,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        result = await self._request(
            self.FLIGHT_URL,
            {
                "departure": resolve_city_iata(from_city),
                "arrival": resolve_city_iata(to_city),
                "departureDate": default_travel_date(travel_date),
                "maxSegments": "0",
            },
            self.flight_api_key,
        )

        if not isinstance(result, dict):
            return []

        flight_info = result.get("flightInfo") or result.get("flightinfo") or []
        if isinstance(flight_info, dict):
            flight_info = [flight_info]

        flights = [self._normalize_flight(item) for item in flight_info if isinstance(item, dict)]
        return flights[:limit]
