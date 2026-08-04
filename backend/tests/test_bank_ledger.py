from httpx import AsyncClient


async def test_bank_ledger_crud_lifecycle(client: AsyncClient, bank_account_id: int) -> None:
    create_resp = await client.post(
        "/api/v1/bank-ledger",
        json={"account_id": bank_account_id, "direction": "credit", "amount": "100.00"},
    )
    assert create_resp.status_code == 201
    entry = create_resp.json()
    assert entry["direction"] == "credit"
    entry_id = entry["id"]

    get_resp = await client.get(f"/api/v1/bank-ledger/{entry_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["amount"] == "100.00"

    patch_resp = await client.patch(
        f"/api/v1/bank-ledger/{entry_id}", json={"description": "paycheck"}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["description"] == "paycheck"

    delete_resp = await client.delete(f"/api/v1/bank-ledger/{entry_id}")
    assert delete_resp.status_code == 204

    missing_resp = await client.get(f"/api/v1/bank-ledger/{entry_id}")
    assert missing_resp.status_code == 404


async def test_bank_ledger_rejects_non_positive_amount(
    client: AsyncClient, bank_account_id: int
) -> None:
    resp = await client.post(
        "/api/v1/bank-ledger",
        json={"account_id": bank_account_id, "direction": "credit", "amount": "0"},
    )
    assert resp.status_code == 422
