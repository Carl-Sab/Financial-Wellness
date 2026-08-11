"""Auth/ownership tests for GET /api/v1/analysis/mood-spend-correlation.

Not exercised end-to-end with real correlation data here — that path
renders matplotlib plots and is expensive to set up per test; this file
only checks the auth gate and that a user with no linked-checkin
transactions of their own never sees another user's, without ever
triggering the plotting path (transaction_count == 0 returns before any
plot is generated — see analysis.py).
"""

from collections.abc import Awaitable, Callable
from typing import Any

from httpx import AsyncClient


async def test_mood_spend_correlation_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/analysis/mood-spend-correlation")
    assert resp.status_code == 401


async def test_user_b_sees_no_transactions_scoped_to_user_a(
    client: AsyncClient,
    make_authed_user: Callable[[], Awaitable[tuple[str, dict[str, str]]]],
) -> None:
    _user_a, headers_a = await make_authed_user()
    _user_b, headers_b = await make_authed_user()

    checkin_payload: dict[str, Any] = {
        "category_code": "groceries",
        "valence": "neutral",
        "heart_rate": 80,
    }
    checkin_resp = await client.post(
        "/api/v1/checkins", json=checkin_payload, headers=headers_a
    )
    assert checkin_resp.status_code == 201, checkin_resp.text
    checkin_id = checkin_resp.json()["id"]

    txn_resp = await client.post(
        "/api/v1/transactions",
        json={"category_code": "groceries", "amount": "25.00", "checkin_id": checkin_id},
        headers=headers_a,
    )
    assert txn_resp.status_code == 201, txn_resp.text

    # B has none of their own linked-checkin transactions — must come back
    # empty regardless of what A has.
    b_resp = await client.get("/api/v1/analysis/mood-spend-correlation", headers=headers_b)
    assert b_resp.status_code == 200
    assert b_resp.json()["transaction_count"] == 0
