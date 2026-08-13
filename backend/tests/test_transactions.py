from collections.abc import Awaitable, Callable

from httpx import AsyncClient


async def test_transaction_crud_lifecycle(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    create_resp = await client.post(
        "/api/v1/transactions",
        json={"category_code": "groceries", "amount": "42.50"},
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    transaction = create_resp.json()
    assert transaction["amount"] == "42.50"
    assert transaction["account_id"] is not None
    assert transaction["direction"] == "debit"
    transaction_id = transaction["id"]

    get_resp = await client.get(f"/api/v1/transactions/{transaction_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["category_code"] == "groceries"

    patch_resp = await client.patch(
        f"/api/v1/transactions/{transaction_id}",
        json={"amount": "50.00"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["amount"] == "50.00"
    assert "merchant_name" not in patch_resp.json()
    assert "was_planned" not in patch_resp.json()

    delete_resp = await client.delete(f"/api/v1/transactions/{transaction_id}", headers=headers)
    assert delete_resp.status_code == 204

    missing_resp = await client.get(f"/api/v1/transactions/{transaction_id}", headers=headers)
    assert missing_resp.status_code == 404


async def test_create_transaction_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/transactions", json={"category_code": "groceries", "amount": "42.50"}
    )
    assert resp.status_code == 401


async def test_list_transactions_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/transactions")
    assert resp.status_code == 401


async def test_created_transaction_belongs_to_the_authenticated_user(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    user_id, headers = authed_user
    create_resp = await client.post(
        "/api/v1/transactions",
        json={"category_code": "groceries", "amount": "10.00"},
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    assert create_resp.json()["user_id"] == user_id


async def test_user_b_cannot_read_user_a_transaction(
    client: AsyncClient,
    make_authed_user: Callable[[], Awaitable[tuple[str, dict[str, str]]]],
) -> None:
    _user_a, headers_a = await make_authed_user()
    _user_b, headers_b = await make_authed_user()

    create_resp = await client.post(
        "/api/v1/transactions",
        json={"category_code": "groceries", "amount": "42.50"},
        headers=headers_a,
    )
    transaction_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/transactions/{transaction_id}", headers=headers_b)
    assert get_resp.status_code == 404

    patch_resp = await client.patch(
        f"/api/v1/transactions/{transaction_id}",
        json={"amount": "99.00"},
        headers=headers_b,
    )
    assert patch_resp.status_code == 404

    delete_resp = await client.delete(f"/api/v1/transactions/{transaction_id}", headers=headers_b)
    assert delete_resp.status_code == 404

    still_there = await client.get(f"/api/v1/transactions/{transaction_id}", headers=headers_a)
    assert still_there.status_code == 200


async def test_list_transactions_only_returns_the_authenticated_users_own(
    client: AsyncClient,
    make_authed_user: Callable[[], Awaitable[tuple[str, dict[str, str]]]],
) -> None:
    _user_a, headers_a = await make_authed_user()
    _user_b, headers_b = await make_authed_user()

    await client.post(
        "/api/v1/transactions",
        json={"category_code": "groceries", "amount": "42.50"},
        headers=headers_a,
    )

    b_transactions = (await client.get("/api/v1/transactions", headers=headers_b)).json()
    assert b_transactions == []


async def test_credit_and_debit_rows_share_the_same_transaction_api(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    account = (await client.get("/api/v1/bank-accounts", headers=headers)).json()[0]

    credit = await client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "direction": "credit",
            "amount": "500.00",
            "description": "Salary",
        },
        headers=headers,
    )
    debit = await client.post(
        "/api/v1/transactions",
        json={
            "account_id": account["id"],
            "direction": "debit",
            "amount": "75.00",
            "category_code": "groceries",
        },
        headers=headers,
    )

    assert credit.status_code == 201, credit.text
    assert credit.json()["category_code"] is None
    assert debit.status_code == 201, debit.text
    balance = await client.get(
        f"/api/v1/bank-accounts/{account['id']}/balance", headers=headers
    )
    assert balance.json()["balance"] == "425.00"


async def test_cannot_record_transaction_against_another_users_account(
    client: AsyncClient,
    make_authed_user: Callable[[], Awaitable[tuple[str, dict[str, str]]]],
) -> None:
    _user_a, headers_a = await make_authed_user()
    _user_b, headers_b = await make_authed_user()
    account_a = (await client.get("/api/v1/bank-accounts", headers=headers_a)).json()[0]

    response = await client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_a["id"],
            "direction": "debit",
            "amount": "10.00",
            "category_code": "groceries",
        },
        headers=headers_b,
    )

    assert response.status_code == 404
