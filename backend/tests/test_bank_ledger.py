from collections.abc import Awaitable, Callable

from httpx import AsyncClient


async def test_bank_ledger_crud_lifecycle(
    client: AsyncClient, authed_bank_account: tuple[int, dict[str, str]]
) -> None:
    account_id, headers = authed_bank_account
    create_resp = await client.post(
        "/api/v1/bank-ledger",
        json={"account_id": account_id, "direction": "credit", "amount": "100.00"},
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    entry = create_resp.json()
    assert entry["direction"] == "credit"
    entry_id = entry["id"]

    get_resp = await client.get(f"/api/v1/bank-ledger/{entry_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["amount"] == "100.00"

    patch_resp = await client.patch(
        f"/api/v1/bank-ledger/{entry_id}", json={"description": "paycheck"}, headers=headers
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["description"] == "paycheck"

    delete_resp = await client.delete(f"/api/v1/bank-ledger/{entry_id}", headers=headers)
    assert delete_resp.status_code == 204

    missing_resp = await client.get(f"/api/v1/bank-ledger/{entry_id}", headers=headers)
    assert missing_resp.status_code == 404


async def test_bank_ledger_rejects_non_positive_amount(
    client: AsyncClient, authed_bank_account: tuple[int, dict[str, str]]
) -> None:
    account_id, headers = authed_bank_account
    resp = await client.post(
        "/api/v1/bank-ledger",
        json={"account_id": account_id, "direction": "credit", "amount": "0"},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_create_bank_ledger_entry_unauthenticated_returns_401(
    client: AsyncClient, authed_bank_account: tuple[int, dict[str, str]]
) -> None:
    account_id, _headers = authed_bank_account
    resp = await client.post(
        "/api/v1/bank-ledger",
        json={"account_id": account_id, "direction": "credit", "amount": "100.00"},
    )
    assert resp.status_code == 401


async def test_list_bank_ledger_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/bank-ledger")
    assert resp.status_code == 401


async def test_cannot_create_ledger_entry_against_another_users_account(
    client: AsyncClient,
    authed_bank_account: tuple[int, dict[str, str]],
    make_authed_user: Callable[[], Awaitable[tuple[str, dict[str, str]]]],
) -> None:
    """The account_id in the body is user A's; the caller is B — 404, not
    403, since B shouldn't learn that account_id belongs to someone."""
    account_id, _headers_a = authed_bank_account
    _user_b, headers_b = await make_authed_user()

    resp = await client.post(
        "/api/v1/bank-ledger",
        json={"account_id": account_id, "direction": "credit", "amount": "50.00"},
        headers=headers_b,
    )
    assert resp.status_code == 404


async def test_user_b_cannot_read_user_a_ledger_entry(
    client: AsyncClient,
    authed_bank_account: tuple[int, dict[str, str]],
    make_authed_user: Callable[[], Awaitable[tuple[str, dict[str, str]]]],
) -> None:
    account_id, headers_a = authed_bank_account
    _user_b, headers_b = await make_authed_user()

    create_resp = await client.post(
        "/api/v1/bank-ledger",
        json={"account_id": account_id, "direction": "credit", "amount": "75.00"},
        headers=headers_a,
    )
    entry_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/bank-ledger/{entry_id}", headers=headers_b)
    assert get_resp.status_code == 404

    patch_resp = await client.patch(
        f"/api/v1/bank-ledger/{entry_id}", json={"description": "not yours"}, headers=headers_b
    )
    assert patch_resp.status_code == 404

    delete_resp = await client.delete(f"/api/v1/bank-ledger/{entry_id}", headers=headers_b)
    assert delete_resp.status_code == 404

    still_there = await client.get(f"/api/v1/bank-ledger/{entry_id}", headers=headers_a)
    assert still_there.status_code == 200


async def test_list_bank_ledger_only_returns_the_authenticated_users_own(
    client: AsyncClient,
    authed_bank_account: tuple[int, dict[str, str]],
    make_authed_user: Callable[[], Awaitable[tuple[str, dict[str, str]]]],
) -> None:
    account_id, headers_a = authed_bank_account
    _user_b, headers_b = await make_authed_user()

    await client.post(
        "/api/v1/bank-ledger",
        json={"account_id": account_id, "direction": "credit", "amount": "10.00"},
        headers=headers_a,
    )

    b_entries = (await client.get("/api/v1/bank-ledger", headers=headers_b)).json()
    assert b_entries == []
