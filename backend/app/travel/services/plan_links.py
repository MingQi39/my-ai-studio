"""Navigation link helpers for travel plan export."""

from __future__ import annotations

from urllib.parse import quote

from app.travel.itinerary_models import PlanLocation, StructuredTravelPlan


def build_amap_search_url(
    name: str,
    *,
    address: str | None = None,
    city: str | None = None,
) -> str:
    query = f"{name} {address}".strip() if address else name.strip()
    url = f"https://uri.amap.com/search?query={quote(query)}"
    if city:
        url += f"&city={quote(city)}"
    return url


def collect_plan_locations(plan: StructuredTravelPlan) -> list[dict[str, str]]:
    seen: set[str] = set()
    locations: list[dict[str, str]] = []

    def add(name: str, address: str | None = None, category: str = "地点") -> None:
        key = f"{name}|{address or ''}"
        if not name.strip() or key in seen:
            return
        seen.add(key)
        locations.append(
            {
                "name": name.strip(),
                "address": (address or "").strip(),
                "category": category,
                "url": build_amap_search_url(name, address=address, city=plan.destination),
            }
        )

    for day in plan.daily_itinerary:
        for activity in day.activities:
            if activity.location:
                add(activity.location.name, activity.location.address, "景点/活动")
            elif activity.title:
                add(activity.title, None, "景点/活动")

    for item in plan.accommodations:
        add(item.name, item.address, "住宿")

    return locations
