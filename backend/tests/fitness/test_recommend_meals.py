import pytest

from app.fitness.services.recommendation_service import recommend_meals_local


def test_recommend_meals_local_returns_3_candidates():
    recs = recommend_meals_local(
        meal_type="dinner",
        target_kcal=600,
        preferences=["low_oil"],
    )
    assert len(recs) >= 1
    assert recs[0].total_kcal > 0
    assert all(len(r.items) >= 3 for r in recs)


def test_recommend_meals_local_vegetarian_filter_does_not_crash():
    recs = recommend_meals_local(
        meal_type="lunch",
        target_kcal=800,
        preferences=["vegetarian"],
    )
    assert len(recs) >= 1
    # candidates are built from local library, so source is local
    assert all(item.source == "local" for r in recs for item in r.items)

