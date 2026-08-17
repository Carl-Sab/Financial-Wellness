"""Tests for the monthly-goal rollover feature: GET/POST /api/v1/goals/monthly
and the provisional carry-forward it drives in /api/v1/spending/summary.
"""

import calendar
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from httpx import AsyncClient

from wellness.api.v1.monthly_goals import (
    OVERSPEND_REDUCTION_FACTOR,
    SUGGESTION_FLOOR_FACTOR,
    UNDERSPEND_TIGHTEN_FACTOR,
    _suggest_target,
)


def _quantize(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# --- Pure suggestion-formula tests -----------------------------------------


def test_suggestion_reduces_20_percent_from_actual_spend_when_over_budget() -> None:
    suggested = _suggest_target(
        last_month_spent=Decimal("1000.00"),
        last_month_target=Decimal("800.00"),
        floor_amount=Decimal("0.00"),
    )
    assert suggested == _quantize(Decimal("1000.00") * OVERSPEND_REDUCTION_FACTOR)


def test_suggestion_tightens_halfway_toward_spend_when_under_budget() -> None:
    """Coming in under target must still move the number, but never all the
    way to actual spend — halfway, per the agreed formula."""
    suggested = _suggest_target(
        last_month_spent=Decimal("400.00"),
        last_month_target=Decimal("1000.00"),
        floor_amount=Decimal("0.00"),
    )
    gap = Decimal("1000.00") - Decimal("400.00")
    expected = Decimal("1000.00") - gap * UNDERSPEND_TIGHTEN_FACTOR
    assert suggested == _quantize(expected)
    assert suggested == Decimal("700.00")


def test_suggestion_never_drops_below_the_floor() -> None:
    suggested = _suggest_target(
        last_month_spent=Decimal("10.00"),
        last_month_target=Decimal("50.00"),
        floor_amount=Decimal("500.00"),
    )
    assert suggested == Decimal("500.00")


def test_floor_factor_is_half() -> None:
    assert SUGGESTION_FLOOR_FACTOR == Decimal("0.5")


# --- Integration tests -------------------------------------------------


async def _rewind_goal_to_last_month(
    client: AsyncClient, headers: dict[str, str], goal_id: int
) -> tuple[date, date]:
    """Backdate the onboarding-created goal so it no longer covers today,
    simulating "the month has rolled over and nothing new has been set yet"
    without waiting for real time to pass."""
    today = date.today()
    this_month_start = today.replace(day=1)
    prev_month_end = this_month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)

    patch_resp = await client.patch(
        f"/api/v1/goals/{goal_id}",
        json={"starts_on": prev_month_start.isoformat(), "ends_on": prev_month_end.isoformat()},
        headers=headers,
    )
    assert patch_resp.status_code == 200, patch_resp.text
    return prev_month_start, prev_month_end


async def test_needs_setup_when_no_goal_covers_the_current_month(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    budget_resp = await client.post(
        "/api/v1/onboarding/budget", json={"monthly_budget": "1000.00"}, headers=headers
    )
    goal_id = budget_resp.json()["id"]
    await _rewind_goal_to_last_month(client, headers, goal_id)

    status_resp = await client.get("/api/v1/goals/monthly/current", headers=headers)
    assert status_resp.status_code == 200, status_resp.text
    body = status_resp.json()
    assert body["status"] == "needs_setup"
    assert body["goal"] is None
    assert body["suggestion"]["currency"] == "LBP"
    # No transactions logged last month -> spent (0) < target -> tightens
    # halfway toward 0, i.e. suggested = target / 2 = 500, above the floor
    # (500, since the original signup budget is itself 1000 and the floor is
    # half of that) -- so the floor and the tightened figure coincide here.
    assert Decimal(body["suggestion"]["amount"]) == Decimal("500.00")
    assert body["suggestion"]["basis"] == "tighten_from_underspend"


async def test_accept_suggestion_creates_goal_and_deactivates_the_old_one(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    budget_resp = await client.post(
        "/api/v1/onboarding/budget", json={"monthly_budget": "1000.00"}, headers=headers
    )
    old_goal_id = budget_resp.json()["id"]
    await _rewind_goal_to_last_month(client, headers, old_goal_id)

    accept_resp = await client.post(
        "/api/v1/goals/monthly", json={"accept_suggestion": True}, headers=headers
    )
    assert accept_resp.status_code == 201, accept_resp.text
    new_goal = accept_resp.json()
    assert new_goal["target_amount"] == "500.00"
    assert new_goal["starts_on"] == date.today().isoformat()
    days_in_month = calendar.monthrange(date.today().year, date.today().month)[1]
    assert new_goal["ends_on"] == date.today().replace(day=days_in_month).isoformat()
    assert new_goal["is_active"] is True

    old_goal_resp = await client.get(f"/api/v1/goals/{old_goal_id}", headers=headers)
    assert old_goal_resp.json()["is_active"] is False

    status_resp = await client.get("/api/v1/goals/monthly/current", headers=headers)
    body = status_resp.json()
    assert body["status"] == "active"
    assert body["goal"]["id"] == new_goal["id"]

    second_accept = await client.post(
        "/api/v1/goals/monthly", json={"accept_suggestion": True}, headers=headers
    )
    assert second_accept.status_code == 409


async def test_custom_target_when_needs_setup(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    budget_resp = await client.post(
        "/api/v1/onboarding/budget", json={"monthly_budget": "1000.00"}, headers=headers
    )
    await _rewind_goal_to_last_month(client, headers, budget_resp.json()["id"])

    custom_resp = await client.post(
        "/api/v1/goals/monthly",
        json={"target_amount": "1234.00", "currency": "USD"},
        headers=headers,
    )
    assert custom_resp.status_code == 201, custom_resp.text
    assert custom_resp.json()["target_amount"] == "1234.00"
    assert custom_resp.json()["currency"] == "USD"


async def test_custom_target_requires_a_value_unless_accepting(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    budget_resp = await client.post(
        "/api/v1/onboarding/budget", json={"monthly_budget": "1000.00"}, headers=headers
    )
    await _rewind_goal_to_last_month(client, headers, budget_resp.json()["id"])

    resp = await client.post("/api/v1/goals/monthly", json={}, headers=headers)
    assert resp.status_code == 400


async def test_new_monthly_goal_starts_on_creation_day_not_month_start(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    """Decision: a monthly goal set mid-month is prorated from the day it's
    actually created (matching onboarding.py's existing first-budget
    behavior), not backdated to the 1st. Confirmed two ways: the stored
    starts_on, and that the spending summary's monthly target reflects the
    same day-by-day proration _derived_target already applies elsewhere."""
    _user_id, headers = authed_user
    budget_resp = await client.post(
        "/api/v1/onboarding/budget", json={"monthly_budget": "3100000.00"}, headers=headers
    )
    await _rewind_goal_to_last_month(client, headers, budget_resp.json()["id"])

    create_resp = await client.post(
        "/api/v1/goals/monthly", json={"target_amount": "3100000.00"}, headers=headers
    )
    assert create_resp.status_code == 201, create_resp.text
    today = date.today()
    assert create_resp.json()["starts_on"] == today.isoformat()

    txn_resp = await client.post(
        "/api/v1/transactions",
        json={"category_code": "groceries", "amount": "1000.00"},
        headers=headers,
    )
    assert txn_resp.status_code == 201, txn_resp.text

    summary = (await client.get("/api/v1/spending/summary", headers=headers)).json()

    month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    expected_target = Decimal("0")
    day = today
    while day <= month_end:
        days_in_month = calendar.monthrange(day.year, day.month)[1]
        expected_target += Decimal("3100000.00") / Decimal(days_in_month)
        day += timedelta(days=1)
    expected_target = _quantize(expected_target)

    assert Decimal(summary["monthly"]["target"]) == expected_target
    assert summary["monthly"]["is_provisional"] is False
    # If starts_on had been backdated to the 1st instead, the target would
    # equal the full 3,100,000 whenever today isn't the 1st — guard against
    # that regression explicitly.
    if today.day != 1:
        assert expected_target < Decimal("3100000.00")


async def test_provisional_carry_forward_before_the_user_sets_this_months_goal(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    """During the gap between rollover and the user actually setting this
    month's goal, Bank/Home should show last month's target as a provisional
    figure rather than 'no budget set'."""
    _user_id, headers = authed_user
    budget_resp = await client.post(
        "/api/v1/onboarding/budget", json={"monthly_budget": "900.00"}, headers=headers
    )
    await _rewind_goal_to_last_month(client, headers, budget_resp.json()["id"])

    status_resp = await client.get("/api/v1/goals/monthly/current", headers=headers)
    assert status_resp.json()["status"] == "needs_setup"

    summary = (await client.get("/api/v1/spending/summary", headers=headers)).json()
    assert summary["monthly"]["is_provisional"] is True
    assert Decimal(summary["monthly"]["target"]) == Decimal("900.00")
    assert summary["daily"]["is_provisional"] is True
    assert summary["weekly"]["is_provisional"] is True
