from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from httpx import AsyncClient

from wellness.config import get_settings
from wellness.schemas.analysis import DailyMoodPoint
from wellness.services.correlation_feedback import (
    build_template_summary,
    calculate_correlations,
)

ANCHOR = "2026-08-12"


async def _set_august_budget(client: AsyncClient, headers: dict[str, str]) -> None:
    response = await client.post(
        "/api/v1/goals",
        json={
            "goal_type": "monthly_budget",
            "target_amount": "3100.00",
            "currency": "LBP",
            "period": "monthly",
            "starts_on": "2026-08-01",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text


async def _checkin(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    valence: str,
    arousal: int,
    category: str = "groceries",
) -> int:
    response = await client.post(
        "/api/v1/checkins",
        json={
            "category_code": category,
            "valence": valence,
            "arousal_input_mode": "manual",
            "arousal_z": arousal,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


async def _transaction(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    amount: str,
    category: str,
    checkin_id: int | None = None,
) -> None:
    response = await client.post(
        "/api/v1/transactions",
        json={
            "amount": amount,
            "category_code": category,
            "checkin_id": checkin_id,
            "occurred_at": "2026-08-12T12:00:00Z",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text


async def _statistics(
    client: AsyncClient,
    headers: dict[str, str],
    view: str = "weekly",
    category_view: str = "yearly",
) -> dict[str, Any]:
    response = await client.get(
        "/api/v1/analysis/statistics",
        params={
            "view": view,
            "anchor": ANCHOR,
            "category_view": category_view,
            "category_anchor": ANCHOR,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


async def test_statistics_requires_authentication(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/analysis/statistics", params={"view": "weekly", "anchor": ANCHOR}
    )
    assert response.status_code == 401


async def test_correlation_summary_requires_authentication(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/analysis/correlation-summary",
        json={"view": "weekly", "anchor": ANCHOR},
    )
    assert response.status_code == 401


async def test_correlation_summary_has_a_safe_fallback_without_history(
    client: AsyncClient,
    authed_user: tuple[str, dict[str, str]],
    monkeypatch: Any,
) -> None:
    _user_id, headers = authed_user
    monkeypatch.setattr(get_settings(), "gateway_api_key", None)
    response = await client.post(
        "/api/v1/analysis/correlation-summary",
        json={"view": "weekly", "anchor": ANCHOR},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "template"
    assert {item["classification"] for item in body["correlations"]} == {
        "insufficient_data"
    }
    assert "not enough" in body["summary"]["overall"].lower()


def test_correlation_calculation_detects_direction_without_exposing_jargon() -> None:
    start = date(2026, 7, 1)
    points = [
        DailyMoodPoint(
            day=start + timedelta(days=index),
            positive_mood=index / 13 * 2,
            negative_mood=2 - index / 13 * 2,
            arousal=index / 13 * 4 - 2,
            normalized_spending=0.5 + index / 13 * 3,
            spent_amount=Decimal(100 + index),
            transaction_count=2,
            checkin_transaction_count=2,
            checkin_spend_coverage=1,
        )
        for index in range(14)
    ]
    results = calculate_correlations(points)
    classifications = {result.metric: result.classification for result in results}
    assert classifications == {
        "positive_mood": "clear_positive_pattern",
        "negative_mood": "clear_negative_pattern",
        "arousal": "clear_positive_pattern",
    }

    summary = build_template_summary(results)
    rendered = " ".join(summary.model_dump().values()).lower()
    assert "correlation" not in rendered
    assert "p-value" not in rendered


async def test_daily_point_uses_amount_weighted_mood_and_total_daily_spending(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    await _set_august_budget(client, headers)
    positive = await _checkin(client, headers, valence="very_pleasant", arousal=-2)
    negative = await _checkin(
        client, headers, valence="unpleasant", arousal=2, category="restaurant"
    )
    await _transaction(
        client, headers, amount="25.00", category="groceries", checkin_id=positive
    )
    await _transaction(
        client, headers, amount="75.00", category="restaurant", checkin_id=negative
    )
    # This purchase counts toward spending but is not incorrectly treated as mood zero.
    await _transaction(client, headers, amount="100.00", category="groceries")

    body = await _statistics(client, headers)
    point = body["daily_mood"][0]
    assert point["day"] == ANCHOR
    assert point["positive_mood"] == 0.5
    assert point["negative_mood"] == 0.75
    assert point["arousal"] == 1.0
    assert point["normalized_spending"] == 4.0
    assert point["transaction_count"] == 3
    assert point["checkin_transaction_count"] == 2
    assert point["checkin_spend_coverage"] == 0.5

    day = next(bucket for bucket in body["review"] if bucket["period_start"] == ANCHOR)
    assert Decimal(day["spent_amount"]) == Decimal("200.00")
    assert Decimal(day["budget_amount"]) == Decimal("100.00")
    assert day["normalized_spending"] == 4.0
    assert day["overspent"] is True


async def test_monthly_review_uses_calendar_weeks_and_annual_category_shares(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    await _set_august_budget(client, headers)
    await _transaction(client, headers, amount="25.00", category="groceries")
    await _transaction(client, headers, amount="75.00", category="restaurant")

    body = await _statistics(client, headers, view="monthly")
    assert body["range_start"] == "2026-08-01"
    assert body["range_end"] == "2026-08-31"
    assert [bucket["label"] for bucket in body["review"]] == [
        "Week 1",
        "Week 2",
        "Week 3",
        "Week 4",
        "Week 5",
        "Week 6",
    ]
    assert sum(Decimal(bucket["budget_amount"]) for bucket in body["review"]) == Decimal(
        "3100.00"
    )

    summary = body["category_summary"]
    assert Decimal(summary["total_spent"]) == Decimal("100.00")
    shares = {item["category_code"]: item["share"] for item in summary["categories"]}
    assert shares == {"restaurant": 0.75, "groceries": 0.25}


async def test_category_summary_supports_day_week_month_and_year(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    await _set_august_budget(client, headers)
    await _transaction(client, headers, amount="40.00", category="groceries")

    expected_ranges = {
        "daily": (ANCHOR, ANCHOR),
        "weekly": ("2026-08-10", "2026-08-16"),
        "monthly": ("2026-08-01", "2026-08-31"),
        "yearly": ("2026-01-01", "2026-12-31"),
    }
    for category_view, expected_range in expected_ranges.items():
        body = await _statistics(client, headers, category_view=category_view)
        summary = body["category_summary"]
        assert summary["view"] == category_view
        assert (summary["range_start"], summary["range_end"]) == expected_range
        assert Decimal(summary["total_spent"]) == Decimal("40.00")


async def test_detailed_checkin_contributes_a_resolved_arousal_value(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    await _set_august_budget(client, headers)
    checkin = await client.post(
        "/api/v1/checkins",
        json={
            "category_code": "groceries",
            "valence": "neutral",
            "arousal_input_mode": "detailed",
            "perceived_heart_rate": 1,
            "perceived_heartbeat_steadiness": 0,
            "perceived_sweating": -1,
            "perceived_respiration": 2,
            "perceived_temperature_difference": 1,
        },
        headers=headers,
    )
    assert checkin.status_code == 201, checkin.text
    await _transaction(
        client,
        headers,
        amount="50.00",
        category="groceries",
        checkin_id=int(checkin.json()["id"]),
    )

    body = await _statistics(client, headers)
    assert len(body["daily_mood"]) == 1
    assert body["daily_mood"][0]["arousal"] is not None
    assert -2 <= body["daily_mood"][0]["arousal"] <= 2
