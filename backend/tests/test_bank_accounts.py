from collections.abc import Callable

from httpx import AsyncClient


async def test_bank_account_crud_lifecycle(
    client: AsyncClient, user_id: str, unique: Callable[[str], str]
) -> None:
    account_number = unique("ACC")
    create_resp = await client.post(
        "/api/v1/bank-accounts", json={"user_id": user_id, "account_number": account_number}
    )
    assert create_resp.status_code == 201
    account_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/bank-accounts/{account_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["account_number"] == account_number

    patch_resp = await client.patch(
        f"/api/v1/bank-accounts/{account_id}", json={"is_active": False}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_active"] is False

    delete_resp = await client.delete(f"/api/v1/bank-accounts/{account_id}")
    assert delete_resp.status_code == 204

    missing_resp = await client.get(f"/api/v1/bank-accounts/{account_id}")
    assert missing_resp.status_code == 404


async def test_bank_account_duplicate_account_number_is_409(
    client: AsyncClient, user_id: str, unique: Callable[[str], str]
) -> None:
    account_number = unique("ACC")
    first = await client.post(
        "/api/v1/bank-accounts", json={"user_id": user_id, "account_number": account_number}
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/bank-accounts", json={"user_id": user_id, "account_number": account_number}
    )
    assert second.status_code == 409


async def test_bank_account_balance_sums_ledger(client: AsyncClient, user_id: str) -> None:
    account_resp = await client.post(
        "/api/v1/bank-accounts", json={"user_id": user_id, "account_number": f"BAL-{user_id}"}
    )
    account_id = account_resp.json()["id"]

    await client.post(
        "/api/v1/bank-ledger",
        json={"account_id": account_id, "direction": "credit", "amount": "200.00"},
    )
    await client.post(
        "/api/v1/bank-ledger",
        json={"account_id": account_id, "direction": "debit", "amount": "42.50"},
    )

    balance_resp = await client.get(f"/api/v1/bank-accounts/{account_id}/balance")
    assert balance_resp.status_code == 200
    assert balance_resp.json()["balance"] == "157.50"
