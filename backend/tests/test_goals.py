from datetime import UTC, datetime, timedelta

from httpx import AsyncClient


async def test_goal_crud_lifecycle(client: AsyncClient, user_id: str) -> None:
    create_resp = await client.post(
        "/api/v1/goals",
        json={
            "user_id": user_id,
            "goal_type": "monthly_budget",
            "target_amount": "500.00",
            "period": "monthly",
            "starts_on": "2026-08-01",
        },
    )
    assert create_resp.status_code == 201
    goal = create_resp.json()
    assert goal["target_amount"] == "500.00"
    goal_id = goal["id"]

    get_resp = await client.get(f"/api/v1/goals/{goal_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["goal_type"] == "monthly_budget"

    patch_resp = await client.patch(f"/api/v1/goals/{goal_id}", json={"target_amount": "600.00"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["target_amount"] == "600.00"

    delete_resp = await client.delete(f"/api/v1/goals/{goal_id}")
    assert delete_resp.status_code == 204

    missing_resp = await client.get(f"/api/v1/goals/{goal_id}")
    assert missing_resp.status_code == 404


async def test_goal_progress_sums_transactions_in_period(client: AsyncClient, user_id: str) -> None:
    goal_resp = await client.post(
        "/api/v1/goals",
        json={
            "user_id": user_id,
            "goal_type": "category_cap",
            "category_code": "groceries",
            "target_amount": "100.00",
            "period": "monthly",
            "starts_on": "2026-08-01",
        },
    )
    assert goal_resp.status_code == 201
    goal_id = goal_resp.json()["id"]

    txn_resp = await client.post(
        "/api/v1/transactions",
        json={"user_id": user_id, "category_code": "groceries", "amount": "30.00"},
    )
    assert txn_resp.status_code == 201

    progress_resp = await client.get(f"/api/v1/goals/{goal_id}/progress")
    assert progress_resp.status_code == 200
    progress = progress_resp.json()
    assert progress["spent_amount"] == "30.00"
    assert progress["remaining_amount"] == "70.00"


async def test_weekly_goal_progress_still_works(client: AsyncClient, user_id: str) -> None:
    goal_resp = await client.post(
        "/api/v1/goals",
        json={
            "user_id": user_id,
            "goal_type": "monthly_budget",
            "target_amount": "200.00",
            "period": "weekly",
            "starts_on": "2026-01-01",
        },
    )
    assert goal_resp.status_code == 201
    goal_id = goal_resp.json()["id"]

    await client.post(
        "/api/v1/transactions",
        json={"user_id": user_id, "category_code": "groceries", "amount": "20.00"},
    )

    progress_resp = await client.get(f"/api/v1/goals/{goal_id}/progress")
    assert progress_resp.status_code == 200
    assert progress_resp.json()["spent_amount"] == "20.00"


async def test_daily_goal_progress_covers_only_today_excludes_yesterday(
    client: AsyncClient, user_id: str
) -> None:
    # Pin the user's timezone so the test doesn't depend on whatever
    # timezone the machine running it happens to be in.
    patch_resp = await client.patch(f"/api/v1/users/{user_id}", json={"timezone": "UTC"})
    assert patch_resp.status_code == 200

    goal_resp = await client.post(
        "/api/v1/goals",
        json={
            "user_id": user_id,
            "goal_type": "monthly_budget",
            "target_amount": "50.00",
            "period": "daily",
            "starts_on": "2026-01-01",
        },
    )
    assert goal_resp.status_code == 201
    goal_id = goal_resp.json()["id"]

    today_utc = datetime.now(UTC).date()

    today_txn = await client.post(
        "/api/v1/transactions",
        json={"user_id": user_id, "category_code": "groceries", "amount": "10.00"},
    )
    assert today_txn.status_code == 201

    yesterday_noon = (datetime.now(UTC) - timedelta(days=1)).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    yesterday_txn = await client.post(
        "/api/v1/transactions",
        json={
            "user_id": user_id,
            "category_code": "groceries",
            "amount": "999.00",
            "occurred_at": yesterday_noon.isoformat(),
        },
    )
    assert yesterday_txn.status_code == 201

    progress_resp = await client.get(f"/api/v1/goals/{goal_id}/progress")
    assert progress_resp.status_code == 200
    progress = progress_resp.json()
    assert progress["period_start"] == today_utc.isoformat()
    assert progress["period_end"] == today_utc.isoformat()
    assert progress["spent_amount"] == "10.00"  # yesterday's 999.00 excluded
    assert progress["remaining_amount"] == "40.00"
