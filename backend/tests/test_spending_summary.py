"""Integration tests for GET /api/v1/spending/summary — the bank page's
daily/weekly/monthly spend overview.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
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


async def test_monthly_has_target_and_remaining_daily_and_weekly_are_null(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
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

    assert summary["daily"]["target"] is None
    assert summary["daily"]["remaining"] is None
    assert summary["weekly"]["target"] is None
    assert summary["weekly"]["remaining"] is None

    assert Decimal(summary["monthly"]["target"]) == Decimal("2000000")
    assert Decimal(summary["monthly"]["spent"]) == Decimal("1650000.00")
    assert Decimal(summary["monthly"]["remaining"]) == Decimal("350000.00")


async def test_daily_and_weekly_do_not_inherit_the_monthly_budget(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    """Onboarding only creates a monthly goal — daily/weekly must stay
    null, never a value silently derived by dividing the monthly target."""
    _user_id, headers = authed_user
    await client.post(
        "/api/v1/onboarding/budget", json={"monthly_budget": "3000000"}, headers=headers
    )

    summary = (await client.get("/api/v1/spending/summary", headers=headers)).json()
    assert summary["daily"]["target"] is None
    assert summary["weekly"]["target"] is None


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
