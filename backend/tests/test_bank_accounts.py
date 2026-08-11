from collections.abc import Awaitable, Callable

from httpx import AsyncClient


async def test_bank_account_crud_lifecycle(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]], unique: Callable[[str], str]
) -> None:
    _user_id, headers = authed_user
    account_number = unique("ACC")
    create_resp = await client.post(
        "/api/v1/bank-accounts", json={"account_number": account_number}, headers=headers
    )
    assert create_resp.status_code == 201, create_resp.text
    account_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/bank-accounts/{account_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["account_number"] == account_number

    patch_resp = await client.patch(
        f"/api/v1/bank-accounts/{account_id}", json={"is_active": False}, headers=headers
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_active"] is False

    delete_resp = await client.delete(f"/api/v1/bank-accounts/{account_id}", headers=headers)
    assert delete_resp.status_code == 204

    missing_resp = await client.get(f"/api/v1/bank-accounts/{account_id}", headers=headers)
    assert missing_resp.status_code == 404


async def test_create_bank_account_unauthenticated_returns_401(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    resp = await client.post(
        "/api/v1/bank-accounts", json={"account_number": unique("ACC")}
    )
    assert resp.status_code == 401


async def test_created_bank_account_belongs_to_the_authenticated_user(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]], unique: Callable[[str], str]
) -> None:
    user_id, headers = authed_user
    create_resp = await client.post(
        "/api/v1/bank-accounts", json={"account_number": unique("ACC")}, headers=headers
    )
    assert create_resp.status_code == 201, create_resp.text
    assert create_resp.json()["user_id"] == user_id


async def test_bank_account_duplicate_account_number_is_409(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]], unique: Callable[[str], str]
) -> None:
    _user_id, headers = authed_user
    account_number = unique("ACC")
    first = await client.post(
        "/api/v1/bank-accounts", json={"account_number": account_number}, headers=headers
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/bank-accounts", json={"account_number": account_number}, headers=headers
    )
    assert second.status_code == 409


async def test_bank_account_balance_sums_ledger(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]], unique: Callable[[str], str]
) -> None:
    _user_id, headers = authed_user
    account_resp = await client.post(
        "/api/v1/bank-accounts", json={"account_number": unique("ACC")}, headers=headers
    )
    account_id = account_resp.json()["id"]

    await client.post(
        "/api/v1/bank-ledger",
        json={"account_id": account_id, "direction": "credit", "amount": "200.00"},
        headers=headers,
    )
    await client.post(
        "/api/v1/bank-ledger",
        json={"account_id": account_id, "direction": "debit", "amount": "42.50"},
        headers=headers,
    )

    balance_resp = await client.get(f"/api/v1/bank-accounts/{account_id}/balance", headers=headers)
    assert balance_resp.status_code == 200
    assert balance_resp.json()["balance"] == "157.50"


async def test_user_b_cannot_read_user_a_bank_account(
    client: AsyncClient,
    make_authed_user: Callable[[], Awaitable[tuple[str, dict[str, str]]]],
    unique: Callable[[str], str],
) -> None:
    _user_a, headers_a = await make_authed_user()
    _user_b, headers_b = await make_authed_user()

    create_resp = await client.post(
        "/api/v1/bank-accounts", json={"account_number": unique("ACC")}, headers=headers_a
    )
    account_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/bank-accounts/{account_id}", headers=headers_b)
    assert get_resp.status_code == 404

    patch_resp = await client.patch(
        f"/api/v1/bank-accounts/{account_id}", json={"is_active": False}, headers=headers_b
    )
    assert patch_resp.status_code == 404

    balance_resp = await client.get(
        f"/api/v1/bank-accounts/{account_id}/balance", headers=headers_b
    )
    assert balance_resp.status_code == 404

    delete_resp = await client.delete(f"/api/v1/bank-accounts/{account_id}", headers=headers_b)
    assert delete_resp.status_code == 404

    still_there = await client.get(f"/api/v1/bank-accounts/{account_id}", headers=headers_a)
    assert still_there.status_code == 200


async def test_list_bank_accounts_only_returns_the_authenticated_users_own(
    client: AsyncClient,
    make_authed_user: Callable[[], Awaitable[tuple[str, dict[str, str]]]],
    unique: Callable[[str], str],
) -> None:
    # Registration auto-creates one bank account per user (see auth.py), so
    # a fresh user's list isn't empty — it's exactly their own registration
    # account, never the other user's.
    _user_a, headers_a = await make_authed_user()
    user_b, headers_b = await make_authed_user()

    create_resp = await client.post(
        "/api/v1/bank-accounts", json={"account_number": unique("ACC")}, headers=headers_a
    )
    a_only_account_id = create_resp.json()["id"]

    b_accounts = (await client.get("/api/v1/bank-accounts", headers=headers_b)).json()
    assert all(account["user_id"] == user_b for account in b_accounts)
    assert all(account["id"] != a_only_account_id for account in b_accounts)
