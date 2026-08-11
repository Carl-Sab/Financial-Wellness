from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient


async def test_goal_crud_lifecycle(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    create_resp = await client.post(
        "/api/v1/goals",
        json={
            "goal_type": "monthly_budget",
            "target_amount": "500.00",
            "period": "monthly",
            "starts_on": "2026-08-01",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    goal = create_resp.json()
    assert goal["target_amount"] == "500.00"
    goal_id = goal["id"]

    get_resp = await client.get(f"/api/v1/goals/{goal_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["goal_type"] == "monthly_budget"

    patch_resp = await client.patch(
        f"/api/v1/goals/{goal_id}", json={"target_amount": "600.00"}, headers=headers
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["target_amount"] == "600.00"

    delete_resp = await client.delete(f"/api/v1/goals/{goal_id}", headers=headers)
    assert delete_resp.status_code == 204

    missing_resp = await client.get(f"/api/v1/goals/{goal_id}", headers=headers)
    assert missing_resp.status_code == 404


async def test_create_goal_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/goals",
        json={
            "goal_type": "monthly_budget",
            "target_amount": "500.00",
            "period": "monthly",
            "starts_on": "2026-08-01",
        },
    )
    assert resp.status_code == 401


async def test_list_goals_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/goals")
    assert resp.status_code == 401


async def test_created_goal_belongs_to_the_authenticated_user_not_a_payload_field(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    """The old schema let a caller set user_id directly in the body — that
    field is gone now; user_id is always the authenticated caller's id."""
    user_id, headers = authed_user
    create_resp = await client.post(
        "/api/v1/goals",
        json={
            "goal_type": "monthly_budget",
            "target_amount": "500.00",
            "period": "monthly",
            "starts_on": "2026-08-01",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    assert create_resp.json()["user_id"] == user_id


async def test_user_b_cannot_read_user_a_goal(
    client: AsyncClient,
    make_authed_user: Callable[[], Awaitable[tuple[str, dict[str, str]]]],
) -> None:
    _user_a, headers_a = await make_authed_user()
    _user_b, headers_b = await make_authed_user()

    create_resp = await client.post(
        "/api/v1/goals",
        json={
            "goal_type": "monthly_budget",
            "target_amount": "500.00",
            "period": "monthly",
            "starts_on": "2026-08-01",
        },
        headers=headers_a,
    )
    goal_id = create_resp.json()["id"]

    # 404, not 403 — B shouldn't be able to tell the goal exists at all.
    get_resp = await client.get(f"/api/v1/goals/{goal_id}", headers=headers_b)
    assert get_resp.status_code == 404

    patch_resp = await client.patch(
        f"/api/v1/goals/{goal_id}", json={"target_amount": "1.00"}, headers=headers_b
    )
    assert patch_resp.status_code == 404

    delete_resp = await client.delete(f"/api/v1/goals/{goal_id}", headers=headers_b)
    assert delete_resp.status_code == 404

    progress_resp = await client.get(f"/api/v1/goals/{goal_id}/progress", headers=headers_b)
    assert progress_resp.status_code == 404

    # Still there for A — B's attempts didn't actually delete/modify it.
    still_there = await client.get(f"/api/v1/goals/{goal_id}", headers=headers_a)
    assert still_there.status_code == 200
    assert still_there.json()["target_amount"] == "500.00"


async def test_list_goals_only_returns_the_authenticated_users_own(
    client: AsyncClient,
    make_authed_user: Callable[[], Awaitable[tuple[str, dict[str, str]]]],
) -> None:
    _user_a, headers_a = await make_authed_user()
    _user_b, headers_b = await make_authed_user()

    await client.post(
        "/api/v1/goals",
        json={
            "goal_type": "monthly_budget",
            "target_amount": "500.00",
            "period": "monthly",
            "starts_on": "2026-08-01",
        },
        headers=headers_a,
    )

    b_goals = (await client.get("/api/v1/goals", headers=headers_b)).json()
    assert b_goals == []


async def test_goal_progress_sums_transactions_in_period(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    goal_resp = await client.post(
        "/api/v1/goals",
        json={
            "goal_type": "category_cap",
            "category_code": "groceries",
            "target_amount": "100.00",
            "period": "monthly",
            "starts_on": "2026-08-01",
        },
        headers=headers,
    )
    assert goal_resp.status_code == 201, goal_resp.text
    goal_id = goal_resp.json()["id"]

    txn_resp = await client.post(
        "/api/v1/transactions",
        json={"category_code": "groceries", "amount": "30.00"},
        headers=headers,
    )
    assert txn_resp.status_code == 201

    progress_resp = await client.get(f"/api/v1/goals/{goal_id}/progress", headers=headers)
    assert progress_resp.status_code == 200
    progress = progress_resp.json()
    assert progress["spent_amount"] == "30.00"
    assert progress["remaining_amount"] == "70.00"


async def test_weekly_goal_progress_still_works(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    goal_resp = await client.post(
        "/api/v1/goals",
        json={
            "goal_type": "monthly_budget",
            "target_amount": "200.00",
            "period": "weekly",
            "starts_on": "2026-01-01",
        },
        headers=headers,
    )
    assert goal_resp.status_code == 201, goal_resp.text
    goal_id = goal_resp.json()["id"]

    await client.post(
        "/api/v1/transactions",
        json={"category_code": "groceries", "amount": "20.00"},
        headers=headers,
    )

    progress_resp = await client.get(f"/api/v1/goals/{goal_id}/progress", headers=headers)
    assert progress_resp.status_code == 200
    assert progress_resp.json()["spent_amount"] == "20.00"


async def test_daily_goal_progress_covers_only_today_excludes_yesterday(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    user_id, headers = authed_user
    # Pin the user's timezone so the test doesn't depend on whatever
    # timezone the machine running it happens to be in.
    patch_resp = await client.patch(f"/api/v1/users/{user_id}", json={"timezone": "UTC"})
    assert patch_resp.status_code == 200

    goal_resp = await client.post(
        "/api/v1/goals",
        json={
            "goal_type": "monthly_budget",
            "target_amount": "50.00",
            "period": "daily",
            "starts_on": "2026-01-01",
        },
        headers=headers,
    )
    assert goal_resp.status_code == 201, goal_resp.text
    goal_id = goal_resp.json()["id"]

    today_utc = datetime.now(UTC).date()

    today_txn = await client.post(
        "/api/v1/transactions",
        json={"category_code": "groceries", "amount": "10.00"},
        headers=headers,
    )
    assert today_txn.status_code == 201

    yesterday_noon = (datetime.now(UTC) - timedelta(days=1)).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    yesterday_txn = await client.post(
        "/api/v1/transactions",
        json={
            "category_code": "groceries",
            "amount": "999.00",
            "occurred_at": yesterday_noon.isoformat(),
        },
        headers=headers,
    )
    assert yesterday_txn.status_code == 201

    progress_resp = await client.get(f"/api/v1/goals/{goal_id}/progress", headers=headers)
    assert progress_resp.status_code == 200
    progress = progress_resp.json()
    assert progress["period_start"] == today_utc.isoformat()
    assert progress["period_end"] == today_utc.isoformat()
    assert progress["spent_amount"] == "10.00"  # yesterday's 999.00 excluded
    assert progress["remaining_amount"] == "40.00"
