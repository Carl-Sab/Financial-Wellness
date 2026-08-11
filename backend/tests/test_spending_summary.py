"""Integration tests for GET /api/v1/spending/summary — the bank page's
daily/weekly/monthly spend overview.
"""

import calendar
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from httpx import AsyncClient

_BEIRUT = ZoneInfo("Asia/Beirut")


async def test_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/spending/summary")
    assert resp.status_code == 401


async def test_no_transactions_gets_zeros_not_nulls_or_error(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    resp = await client.get("/api/v1/spending/summary", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    for window in ("daily", "weekly", "monthly"):
        assert Decimal(body[window]["spent"]) == Decimal("0")
    # Registration creates a bank account with no ledger entries — balance
    # is a real, valid zero, not missing data.
    assert Decimal(body["balance"]) == Decimal("0")
    assert body["currency"] == "LBP"


async def test_daily_window_uses_the_users_timezone_not_utc(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    user_id, headers = authed_user
    patch_resp = await client.patch(
        f"/api/v1/users/{user_id}", json={"timezone": "Asia/Beirut"}
    )
    assert patch_resp.status_code == 200

    now_beirut = datetime.now(_BEIRUT)
    beirut_midnight_local = now_beirut.replace(hour=0, minute=0, second=0, microsecond=0)
    beirut_midnight_utc = beirut_midnight_local.astimezone(UTC)

    # Sanity check that this scenario actually proves something: Beirut is
    # always ahead of UTC, so Beirut's local midnight always converts to a
    # UTC timestamp still on UTC's *previous* calendar day. A server that
    # (wrongly) used a UTC calendar-day boundary instead of the user's own
    # timezone would exclude this transaction from "today".
    utc_midnight_today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    assert beirut_midnight_utc < utc_midnight_today

    txn_resp = await client.post(
        "/api/v1/transactions",
        json={
            "category_code": "groceries",
            "amount": "37.00",
            "occurred_at": beirut_midnight_utc.isoformat(),
        },
        headers=headers,
    )
    assert txn_resp.status_code == 201, txn_resp.text

    summary_resp = await client.get("/api/v1/spending/summary", headers=headers)
    assert summary_resp.status_code == 200
    assert Decimal(summary_resp.json()["daily"]["spent"]) == Decimal("37.00")


def _expected_daily_target(monthly_target: Decimal) -> Decimal:
    today = date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    return (monthly_target / Decimal(days_in_month)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def test_weekly_and_daily_targets_derive_from_the_monthly_budget(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    """Onboarding only ever creates a monthly goal — with no explicit
    weekly/daily goal, their targets are derived from it: weekly flat by 4,
    daily by the number of days in the current calendar month."""
    _user_id, headers = authed_user
    budget_resp = await client.post(
        "/api/v1/onboarding/budget", json={"monthly_budget": "2000000"}, headers=headers
    )
    assert budget_resp.status_code == 201, budget_resp.text

    txn_resp = await client.post(
        "/api/v1/transactions",
        json={"category_code": "groceries", "amount": "1650000.00"},
        headers=headers,
    )
    assert txn_resp.status_code == 201, txn_resp.text

    summary = (await client.get("/api/v1/spending/summary", headers=headers)).json()

    expected_daily_target = _expected_daily_target(Decimal("2000000"))
    assert Decimal(summary["daily"]["target"]) == expected_daily_target
    assert Decimal(summary["daily"]["spent"]) == Decimal("1650000.00")
    assert Decimal(summary["daily"]["remaining"]) == expected_daily_target - Decimal("1650000.00")

    assert Decimal(summary["weekly"]["target"]) == Decimal("500000.00")
    assert Decimal(summary["weekly"]["spent"]) == Decimal("1650000.00")
    assert Decimal(summary["weekly"]["remaining"]) == Decimal("500000.00") - Decimal("1650000.00")

    assert Decimal(summary["monthly"]["target"]) == Decimal("2000000")
    assert Decimal(summary["monthly"]["spent"]) == Decimal("1650000.00")
    assert Decimal(summary["monthly"]["remaining"]) == Decimal("350000.00")


async def test_explicit_period_goal_overrides_the_derived_monthly_figure(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    """A weekly/daily goal that actually exists always wins over a figure
    derived by dividing the monthly budget."""
    _user_id, headers = authed_user
    await client.post(
        "/api/v1/onboarding/budget", json={"monthly_budget": "3000000"}, headers=headers
    )
    goal_resp = await client.post(
        "/api/v1/goals",
        json={
            "goal_type": "weekly_budget",
            "target_amount": "999999.00",
            "period": "weekly",
            "starts_on": date.today().isoformat(),
        },
        headers=headers,
    )
    assert goal_resp.status_code == 201, goal_resp.text

    summary = (await client.get("/api/v1/spending/summary", headers=headers)).json()
    assert Decimal(summary["weekly"]["target"]) == Decimal("999999.00")
    # No explicit daily goal — still derived from the monthly budget.
    assert Decimal(summary["daily"]["target"]) == _expected_daily_target(Decimal("3000000"))


async def test_usd_budget_converts_lbp_transactions_at_the_fixed_rate(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    """The account's display currency stays LBP (the default); the budget
    itself is set in USD. Spending logged in LBP must convert to LBP at the
    fixed 90,000:1 rate before comparing against the budget."""
    _user_id, headers = authed_user
    budget_resp = await client.post(
        "/api/v1/onboarding/budget",
        json={"monthly_budget": "100", "currency": "USD"},
        headers=headers,
    )
    assert budget_resp.status_code == 201, budget_resp.text

    txn_resp = await client.post(
        "/api/v1/transactions",
        json={"category_code": "groceries", "amount": "4500000.00", "currency": "LBP"},
        headers=headers,
    )
    assert txn_resp.status_code == 201, txn_resp.text

    summary = (await client.get("/api/v1/spending/summary", headers=headers)).json()
    assert summary["currency"] == "LBP"
    assert Decimal(summary["monthly"]["target"]) == Decimal("9000000.00")
    assert Decimal(summary["monthly"]["spent"]) == Decimal("4500000.00")
    assert Decimal(summary["monthly"]["remaining"]) == Decimal("4500000.00")

    # Regression check: converting $100 -> LBP must happen *before* dividing
    # into daily/weekly shares, not after — dividing in USD first and
    # rounding to the cent, then converting at 90,000:1, compounds a tiny
    # USD rounding error into a large LBP one (e.g. $3.23 vs the true
    # $3.225806... is only a fraction of a cent off, but times 90,000 that's
    # off by hundreds of LBP).
    assert Decimal(summary["weekly"]["target"]) == Decimal("2250000.00")
    assert Decimal(summary["daily"]["target"]) == _expected_daily_target(Decimal("9000000"))


async def test_balance_matches_bank_account_balance_endpoint(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    accounts = (await client.get("/api/v1/bank-accounts", headers=headers)).json()
    assert len(accounts) == 1
    account_id = accounts[0]["id"]

    await client.post(
        "/api/v1/bank-ledger",
        json={"account_id": account_id, "direction": "credit", "amount": "500000.00"},
        headers=headers,
    )
    await client.post(
        "/api/v1/bank-ledger",
        json={"account_id": account_id, "direction": "debit", "amount": "120000.00"},
        headers=headers,
    )

    balance_resp = await client.get(f"/api/v1/bank-accounts/{account_id}/balance", headers=headers)
    summary_resp = await client.get("/api/v1/spending/summary", headers=headers)

    assert Decimal(summary_resp.json()["balance"]) == Decimal(balance_resp.json()["balance"])
    assert Decimal(summary_resp.json()["balance"]) == Decimal("380000.00")


async def test_user_a_summary_never_includes_user_bs_data(
    client: AsyncClient,
    make_authed_user: Callable[[], Awaitable[tuple[str, dict[str, str]]]],
) -> None:
    _user_a, headers_a = await make_authed_user()
    _user_b, headers_b = await make_authed_user()

    a_accounts = (await client.get("/api/v1/bank-accounts", headers=headers_a)).json()
    a_account_id = a_accounts[0]["id"]

    await client.post(
        "/api/v1/transactions",
        json={"category_code": "groceries", "amount": "99999.00"},
        headers=headers_a,
    )
    await client.post(
        "/api/v1/bank-ledger",
        json={"account_id": a_account_id, "direction": "credit", "amount": "5000000.00"},
        headers=headers_a,
    )

    b_summary = (await client.get("/api/v1/spending/summary", headers=headers_b)).json()
    for window in ("daily", "weekly", "monthly"):
        assert Decimal(b_summary[window]["spent"]) == Decimal("0")
    assert Decimal(b_summary["balance"]) == Decimal("0")
