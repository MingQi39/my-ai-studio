"""
Tavily API 客户端
"""
from typing import Any, Dict, List

import httpx

from app.travel.services.exceptions import ExternalAPIError, ExternalAPITimeout


class TavilyClient:
    BASE_URL = "https://api.tavily.com"

    def __init__(self, api_key: str, timeout: int = 10, max_results: int = 5):
        self.api_key = api_key
        self.timeout = timeout
        self.max_results = max_results

    async def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = {"api_key": self.api_key, **payload}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.BASE_URL}{path}", json=body)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise ExternalAPITimeout("Tavily 请求超时") from exc
        except httpx.HTTPError as exc:
            raise ExternalAPIError(f"Tavily 请求失败: {exc}") from exc

        return data

    async def search(self, query: str) -> List[Dict[str, Any]]:
        data = await self._post(
            "/search",
            {
                "query": query,
                "search_depth": "basic",
                "max_results": self.max_results
            }
        )
        results = data.get("results") or []
        return [
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "content": item.get("content"),
                "score": item.get("score"),
                "source": "tavily"
            }
            for item in results
        ]
