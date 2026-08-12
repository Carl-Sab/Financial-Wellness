"""Integration tests for GET /api/v1/analysis/mood-spending.

Exercised entirely through the real check-in/transaction flow — check-in
creation already triggers baseline refresh + arousal scoring (see
tests/test_arousal_scoring.py) — so building a mature baseline here is just
creating enough check-ins, the same way a real client would.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.models.financial import FinancialProfile

TODAY = date.today()
_RANGE = {"from_date": TODAY.isoformat(), "to_date": TODAY.isoformat(), "granularity": "week"}


async def _mood_spending(client: AsyncClient, headers: dict[str, str]) -> Response:
    return await client.get(
        "/api/v1/analysis/mood-spending", params=_RANGE, headers=headers
    )


async def _create_checkin(
    client: AsyncClient, headers: dict[str, str], **fields: Any
) -> dict[str, Any]:
    payload = {"category_code": "groceries", "valence": "neutral", **fields}
    resp = await client.post("/api/v1/checkins", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    result: dict[str, Any] = resp.json()
    return result


async def _create_transaction(
    client: AsyncClient, headers: dict[str, str], **fields: Any
) -> dict[str, Any]:
    payload = {"category_code": "groceries", **fields}
    resp = await client.post("/api/v1/transactions", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    result: dict[str, Any] = resp.json()
    return result


def _bucket(body: dict[str, Any], mood: str) -> dict[str, int | Decimal]:
    """Sums a named bucket across every returned period."""
    transaction_count = 0
    overspend_count = 0
    total_amount = Decimal("0")
    for period in body["periods"]:
        for bucket in period["buckets"]:
            if bucket["mood"] == mood:
                transaction_count += bucket["transaction_count"]
                overspend_count += bucket["overspend_count"]
                total_amount += Decimal(bucket["total_amount"])
    return {
        "transaction_count": transaction_count,
        "overspend_count": overspend_count,
        "total_amount": total_amount,
    }


async def _build_mature_hr_baseline(client: AsyncClient, headers: dict[str, str]) -> None:
    """10 check-ins with varied heart_rate, no transactions attached — just
    enough (>= 8) to make the baseline usable (baseline_factor != 0).
    """
    for hr in (68, 74, 71, 80, 65, 90, 72, 69, 77, 83):
        await _create_checkin(client, headers, heart_rate=hr)


async def test_mood_spending_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/analysis/mood-spending", params=_RANGE)
    assert resp.status_code == 401


async def test_user_with_no_budget_is_excluded_not_crashed(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    await _create_transaction(client, headers, amount="10.00")

    resp = await _mood_spending(client, headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["daily_budget"] == {"amount": None, "source": "none"}
    assert body["periods"] == []


async def test_budget_source_falls_back_through_priority_chain(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]], db_session: AsyncSession
) -> None:
    user_id, headers = authed_user
    # 1. nothing configured -> 'none'
    body = (await _mood_spending(client, headers)).json()
    assert body["daily_budget"]["source"] == "none"

    # 2. a financial_profile -> 'profile', amount = avg_monthly_spend / 30
    import uuid as uuid_module

    db_session.add(
        FinancialProfile(user_id=uuid_module.UUID(user_id), avg_monthly_spend=Decimal("900.00"))
    )
    await db_session.commit()

    body = (await _mood_spending(client, headers)).json()
    assert body["daily_budget"]["source"] == "profile"
    assert Decimal(body["daily_budget"]["amount"]) == Decimal("900.00") / Decimal(30)

    # 3. an active monthly goal outranks the profile -> 'goal_monthly'
    await client.post(
        "/api/v1/goals",
        json={
            "goal_type": "monthly_budget",
            "target_amount": "3000.00",
            "period": "monthly",
            "starts_on": TODAY.isoformat(),
        },
        headers=headers,
    )
    body = (await _mood_spending(client, headers)).json()
    assert body["daily_budget"]["source"] == "goal_monthly"
    assert Decimal(body["daily_budget"]["amount"]) == Decimal("3000.00") / Decimal(30)

    # 4. an active daily goal outranks everything -> 'goal_daily'
    await client.post(
        "/api/v1/goals",
        json={
            "goal_type": "monthly_budget",
            "target_amount": "150.00",
            "period": "daily",
            "starts_on": TODAY.isoformat(),
        },
        headers=headers,
    )
    body = (await _mood_spending(client, headers)).json()
    assert body["daily_budget"]["source"] == "goal_daily"
    assert Decimal(body["daily_budget"]["amount"]) == Decimal("150.00")


async def test_threshold_crossing_transaction_is_flagged_earlier_ones_are_not(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    await client.post(
        "/api/v1/goals",
        json={
            "goal_type": "monthly_budget",
            "target_amount": "100.00",
            "period": "daily",
            "starts_on": TODAY.isoformat(),
        },
        headers=headers,
    )

    ts = f"{TODAY.isoformat()}T09:00:00Z"
    await _create_transaction(client, headers, amount="40.00", occurred_at=ts)
    ts = f"{TODAY.isoformat()}T12:00:00Z"
    await _create_transaction(client, headers, amount="40.00", occurred_at=ts)  # running: 80
    ts = f"{TODAY.isoformat()}T15:00:00Z"
    await _create_transaction(client, headers, amount="40.00", occurred_at=ts)  # running: 120 > 100

    body = (await _mood_spending(client, headers)).json()
    unclassified = _bucket(body, "unclassified")
    assert unclassified["transaction_count"] == 3
    assert unclassified["overspend_count"] == 1


async def test_null_checkin_id_lands_in_unclassified(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    await client.post(
        "/api/v1/goals",
        json={
            "goal_type": "monthly_budget",
            "target_amount": "3000.00",
            "period": "monthly",
            "starts_on": TODAY.isoformat(),
        },
        headers=headers,
    )
    await _create_transaction(client, headers, amount="25.00")

    body = (await _mood_spending(client, headers)).json()
    assert _bucket(body, "unclassified")["transaction_count"] == 1
    for mood in ("stressed", "positive", "negative", "neutral"):
        assert _bucket(body, mood)["transaction_count"] == 0


async def test_unknown_arousal_label_excluded_from_every_bucket(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    await client.post(
        "/api/v1/goals",
        json={
            "goal_type": "monthly_budget",
            "target_amount": "3000.00",
            "period": "monthly",
            "starts_on": TODAY.isoformat(),
        },
        headers=headers,
    )
    # eda_microsiemens: a metric with no baseline anywhere for this user ->
    # metrics_used = 0 -> label 'unknown', regardless of anything else.
    checkin = await _create_checkin(client, headers, eda_microsiemens=5.0, valence="pleasant")
    arousal_resp = await client.get(f"/api/v1/checkins/{checkin['id']}/arousal", headers=headers)
    assert arousal_resp.json()["label"] == "unknown"
    await _create_transaction(client, headers, amount="15.00", checkin_id=checkin["id"])

    body = (await _mood_spending(client, headers)).json()
    for mood in ("stressed", "positive", "negative", "neutral", "unclassified"):
        assert _bucket(body, mood)["transaction_count"] == 0


async def test_unpleasant_and_high_arousal_lands_in_stressed_only(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    await client.post(
        "/api/v1/goals",
        json={
            "goal_type": "monthly_budget",
            "target_amount": "3000.00",
            "period": "monthly",
            "starts_on": TODAY.isoformat(),
        },
        headers=headers,
    )
    await _build_mature_hr_baseline(client, headers)

    checkin = await _create_checkin(client, headers, heart_rate=150, valence="unpleasant")
    arousal_resp = await client.get(f"/api/v1/checkins/{checkin['id']}/arousal", headers=headers)
    assert arousal_resp.json()["label"] == "high"

    await _create_transaction(client, headers, amount="20.00", checkin_id=checkin["id"])

    body = (await _mood_spending(client, headers)).json()
    assert _bucket(body, "stressed")["transaction_count"] == 1
    assert _bucket(body, "negative")["transaction_count"] == 0


async def test_usd_goal_and_lbp_transaction_convert_to_a_common_currency(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    """The account stays LBP (the default); the monthly budget is set in
    USD and the transaction is logged in USD too, on the other side of the
    same 90,000:1 rate — both must land in LBP terms in the response, not
    be summed/compared as if they were the same number in different units."""
    _user_id, headers = authed_user
    await client.post(
        "/api/v1/goals",
        json={
            "goal_type": "monthly_budget",
            "target_amount": "100",
            "currency": "USD",
            "period": "monthly",
            "starts_on": TODAY.isoformat(),
        },
        headers=headers,
    )
    await _create_transaction(client, headers, amount="50", currency="USD")

    body = (await _mood_spending(client, headers)).json()
    assert body["currency"] == "LBP"
    assert body["daily_budget"]["source"] == "goal_monthly"
    # $100/month -> $100 * 90,000 / 30 = 300,000 LBP/day
    assert Decimal(body["daily_budget"]["amount"]) == Decimal("300000.00")

    unclassified = _bucket(body, "unclassified")
    assert unclassified["transaction_count"] == 1
    # $50 -> 4,500,000 LBP
    assert unclassified["total_amount"] == Decimal("4500000.00")


async def test_reconciliation_all_buckets_plus_excluded_equal_total(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    await client.post(
        "/api/v1/goals",
        json={
            "goal_type": "monthly_budget",
            "target_amount": "3000.00",
            "period": "monthly",
            "starts_on": TODAY.isoformat(),
        },
        headers=headers,
    )
    await _build_mature_hr_baseline(client, headers)
    created_total = 0

    # stressed: high arousal, valence irrelevant to the bucket it lands in
    stressed_checkin = await _create_checkin(client, headers, heart_rate=150, valence="unpleasant")
    await _create_transaction(client, headers, amount="10.00", checkin_id=stressed_checkin["id"])
    created_total += 1

    # positive: near-baseline HR (not 'high'), pleasant valence
    positive_checkin = await _create_checkin(client, headers, heart_rate=71, valence="pleasant")
    await _create_transaction(client, headers, amount="11.00", checkin_id=positive_checkin["id"])
    created_total += 1

    # negative: near-baseline HR (not 'high'), unpleasant valence
    negative_checkin = await _create_checkin(client, headers, heart_rate=72, valence="unpleasant")
    await _create_transaction(client, headers, amount="12.00", checkin_id=negative_checkin["id"])
    created_total += 1

    # neutral: near-baseline HR (not 'high'), neutral valence
    neutral_checkin = await _create_checkin(client, headers, heart_rate=70, valence="neutral")
    await _create_transaction(client, headers, amount="13.00", checkin_id=neutral_checkin["id"])
    created_total += 1

    # unclassified: no checkin at all
    await _create_transaction(client, headers, amount="14.00")
    created_total += 1

    # excluded: label 'unknown' via a metric with no established baseline
    excluded_checkin = await _create_checkin(client, headers, eda_microsiemens=3.0)
    await _create_transaction(client, headers, amount="15.00", checkin_id=excluded_checkin["id"])
    excluded_count = 1
    created_total += 1

    body = (await _mood_spending(client, headers)).json()

    stressed = _bucket(body, "stressed")["transaction_count"]
    positive = _bucket(body, "positive")["transaction_count"]
    negative = _bucket(body, "negative")["transaction_count"]
    neutral = _bucket(body, "neutral")["transaction_count"]
    unclassified = _bucket(body, "unclassified")["transaction_count"]

    print(
        "\nRECONCILIATION: "
        f"stressed={stressed} positive={positive} negative={negative} "
        f"neutral={neutral} unclassified={unclassified} excluded={excluded_count} "
        f"-> sum={stressed + positive + negative + neutral + unclassified + excluded_count} "
        f"vs created_total={created_total}"
    )

    assert stressed == 1
    assert positive == 1
    assert negative == 1
    assert neutral == 1
    assert unclassified == 1
    assert (
        stressed + positive + negative + neutral + unclassified + excluded_count
    ) == created_total
