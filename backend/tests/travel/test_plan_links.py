"""Tests for travel plan navigation links."""

from app.travel.itinerary_models import PlanActivity, PlanDay, PlanLocation, StructuredTravelPlan
from app.travel.services.plan_links import build_amap_search_url, collect_plan_locations


def test_build_amap_search_url():
    url = build_amap_search_url("断桥", address="北山街", city="杭州")
    assert url.startswith("https://uri.amap.com/search?")
    assert "query=" in url
    assert "city=" in url


def test_collect_plan_locations_deduplicates():
    plan = StructuredTravelPlan(
        title="杭州游",
        destination="杭州",
        summary="测试",
        daily_itinerary=[
            PlanDay(
                day=1,
                activities=[
                    PlanActivity(
                        title="断桥",
                        location=PlanLocation(name="断桥", address="北山街"),
                    )
                ],
            )
        ],
        accommodations=[PlanLocation(name="断桥", address="北山街")],
    )

    locations = collect_plan_locations(plan)
    assert len(locations) == 1
    assert locations[0]["url"].startswith("https://uri.amap.com/search?")
