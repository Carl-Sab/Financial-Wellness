from httpx import AsyncClient


async def test_transaction_crud_lifecycle(client: AsyncClient, user_id: str) -> None:
    create_resp = await client.post(
        "/api/v1/transactions",
        json={"user_id": user_id, "category_code": "groceries", "amount": "42.50"},
    )
    assert create_resp.status_code == 201
    transaction = create_resp.json()
    assert transaction["amount"] == "42.50"
    transaction_id = transaction["id"]

    get_resp = await client.get(f"/api/v1/transactions/{transaction_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["category_code"] == "groceries"

    patch_resp = await client.patch(
        f"/api/v1/transactions/{transaction_id}", json={"merchant_name": "Corner Store"}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["merchant_name"] == "Corner Store"

    delete_resp = await client.delete(f"/api/v1/transactions/{transaction_id}")
    assert delete_resp.status_code == 204

    missing_resp = await client.get(f"/api/v1/transactions/{transaction_id}")
    assert missing_resp.status_code == 404
