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
