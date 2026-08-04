from httpx import AsyncClient


async def test_checkin_crud_lifecycle(client: AsyncClient, user_id: str) -> None:
    create_resp = await client.post(
        "/api/v1/checkins",
        json={
            "user_id": user_id,
            "category_code": "groceries",
            "valence": "neutral",
            "heart_rate": 80,
        },
    )
    assert create_resp.status_code == 201
    checkin = create_resp.json()
    assert checkin["valence"] == "neutral"
    checkin_id = checkin["id"]

    get_resp = await client.get(f"/api/v1/checkins/{checkin_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["heart_rate"] == 80.0

    patch_resp = await client.patch(f"/api/v1/checkins/{checkin_id}", json={"heart_rate": 90})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["heart_rate"] == 90.0

    delete_resp = await client.delete(f"/api/v1/checkins/{checkin_id}")
    assert delete_resp.status_code == 204

    missing_resp = await client.get(f"/api/v1/checkins/{checkin_id}")
    assert missing_resp.status_code == 404


async def test_checkin_requires_at_least_one_reading(client: AsyncClient, user_id: str) -> None:
    resp = await client.post(
        "/api/v1/checkins",
        json={"user_id": user_id, "category_code": "groceries", "valence": "neutral"},
    )
    assert resp.status_code == 422
