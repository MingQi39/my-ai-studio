"""
高德地图 API 客户端
"""
import re
from typing import Any, Dict, List

import httpx

from app.travel.services.exceptions import ExternalAPIError, ExternalAPITimeout


def _parse_price(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", text.replace(",", ""))
    return float(match.group(1)) if match else None


class AMapClient:
    BASE_URL = "https://restapi.amap.com"

    def __init__(self, api_key: str, timeout: int = 10):
        self.api_key = api_key
        self.timeout = timeout

    async def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        query = {"key": self.api_key, **params}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.BASE_URL}{path}", params=query)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise ExternalAPITimeout("高德 API 请求超时") from exc
        except httpx.HTTPError as exc:
            raise ExternalAPIError(f"高德 API 请求失败: {exc}") from exc

        if str(data.get("status", "0")) != "1":
            info = data.get("info") or "高德 API 返回错误"
            raise ExternalAPIError(str(info))

        return data

    async def geocode_city(self, city: str) -> Dict[str, str]:
        data = await self._get("/v3/geocode/geo", {"address": city})
        geocodes = data.get("geocodes") or []
        if not geocodes:
            raise ExternalAPIError(f"未找到城市: {city}")

        first = geocodes[0]
        return {
            "city": first.get("city") or city,
            "adcode": first.get("adcode") or "",
            "location": first.get("location") or "",
        }

    async def get_weather(self, city: str, date: str | None = None) -> Dict[str, Any]:
        geo = await self.geocode_city(city)
        data = await self._get(
            "/v3/weather/weatherInfo",
            {
                "city": geo["adcode"],
                "extensions": "all" if date else "base",
            },
        )

        lives = data.get("lives") or []
        if lives:
            live = lives[0]
            return {
                "city": live.get("city") or geo["city"],
                "date": date or "今天",
                "temperature": live.get("temperature"),
                "weather": live.get("weather"),
                "humidity": live.get("humidity"),
                "wind_direction": live.get("winddirection"),
                "wind_power": live.get("windpower"),
            }

        forecasts = data.get("forecasts") or []
        casts = forecasts[0].get("casts", []) if forecasts else []
        if casts:
            cast = next((item for item in casts if date and item.get("date") == date), casts[0])
            return {
                "city": cast.get("city") or geo["city"],
                "date": cast.get("date") or (date or "今天"),
                "temperature": f"{cast.get('nighttemp', '-')}-{cast.get('daytemp', '-')}",
                "weather": f"{cast.get('dayweather', '')}/{cast.get('nightweather', '')}",
                "humidity": None,
                "wind_direction": cast.get("daywind"),
                "wind_power": cast.get("daypower"),
            }

        raise ExternalAPIError("天气接口返回为空")

    async def get_poi_detail(self, poi_id: str) -> Dict[str, Any]:
        data = await self._get("/v3/place/detail", {"id": poi_id})
        pois = data.get("pois") or []
        if not pois:
            return {}
        return pois[0]

    async def _enrich_pois(self, pois: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
        enriched: List[Dict[str, Any]] = []
        for poi in pois[:limit]:
            poi_id = poi.get("id")
            if not poi_id:
                enriched.append(poi)
                continue
            try:
                detail = await self.get_poi_detail(poi_id)
            except ExternalAPIError:
                enriched.append(poi)
                continue

            biz_ext = detail.get("biz_ext") or {}
            if isinstance(biz_ext, str):
                biz_ext = {}

            rating = _parse_price(biz_ext.get("rating"))
            cost = _parse_price(biz_ext.get("cost"))

            enriched.append({
                **poi,
                "rating": rating,
                "price": cost if "price" in poi else poi.get("price", cost),
                "price_per_night": cost if "price_per_night" in poi else poi.get("price_per_night", cost),
                "opentime": detail.get("opentime") or biz_ext.get("open_time"),
                "photos": [
                    photo.get("url")
                    for photo in (detail.get("photos") or [])
                    if isinstance(photo, dict) and photo.get("url")
                ][:3],
            })
        return enriched

    async def _search_poi(
        self,
        city: str,
        keywords: str,
        *,
        types: str | None = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "keywords": keywords,
            "city": city,
            "citylimit": "true",
            "offset": min(limit, 20),
            "page": 1,
            "extensions": "all",
        }
        if types:
            params["types"] = types

        data = await self._get("/v3/place/text", params)
        pois = data.get("pois") or []
        return [
            {
                "id": poi.get("id"),
                "name": poi.get("name"),
                "address": poi.get("address"),
                "location": poi.get("location"),
                "type": poi.get("type"),
                "tel": poi.get("tel"),
            }
            for poi in pois
        ]

    async def search_attractions(
        self,
        city: str,
        limit: int = 10,
        *,
        enrich_details: bool = False,
    ) -> List[Dict[str, Any]]:
        pois = await self._search_poi(city, "风景名胜", types="110000", limit=limit)
        items = [{**poi, "price": None} for poi in pois]
        if enrich_details:
            return await self._enrich_pois(items, limit=min(limit, 5))
        return items

    async def search_hotels(
        self,
        city: str,
        limit: int = 10,
        *,
        enrich_details: bool = False,
    ) -> List[Dict[str, Any]]:
        pois = await self._search_poi(city, "酒店", types="100000", limit=limit)
        items = [
            {
                "id": poi.get("id"),
                "name": poi.get("name"),
                "price_per_night": None,
                "rating": None,
                "location": poi.get("address") or city,
                "address": poi.get("address"),
                "tel": poi.get("tel"),
                "tags": [t for t in (poi.get("type") or "").split(";") if t][:3],
            }
            for poi in pois
        ]
        if enrich_details:
            return await self._enrich_pois(items, limit=min(limit, 5))
        return items

    async def plan_driving(self, from_city: str, to_city: str) -> Dict[str, Any]:
        origin_geo = await self.geocode_city(from_city)
        dest_geo = await self.geocode_city(to_city)
        data = await self._get(
            "/v3/direction/driving",
            {
                "origin": origin_geo["location"],
                "destination": dest_geo["location"],
                "strategy": 0,
            },
        )

        route = data.get("route") or {}
        paths = route.get("paths") or []
        if not paths:
            raise ExternalAPIError("未找到可用驾车路径")

        first = paths[0]
        return {
            "mode": "driving",
            "distance_m": int(first.get("distance", 0)),
            "duration_s": int(first.get("duration", 0)),
            "origin": origin_geo["city"],
            "destination": dest_geo["city"],
            "source": "amap",
        }
