"""Integration tests for POST /api/v1/onboarding/budget and GET
/api/v1/onboarding/budget/me — the post-questionnaire budget setup step.
"""

from collections.abc import Callable

from httpx import AsyncClient

PASSWORD = "hunter2pass"


async def _register_and_login(client: AsyncClient, unique: Callable[[str], str]) -> str:
    email = f"{unique('budget')}@example.com"
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Ada Lovelace",
            "email": email,
            "password": PASSWORD,
            "date_of_birth": "1990-01-01",
        },
    )
    assert register_resp.status_code == 201, register_resp.text

    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert login_resp.status_code == 200, login_resp.text
    token: str = login_resp.json()["access_token"]
    return token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_submit_creates_active_monthly_budget_goal(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    token = await _register_and_login(client, unique)
    resp = await client.post(
        "/api/v1/onboarding/budget",
        json={"monthly_budget": "1500000.00"},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["goal_type"] == "monthly_budget"
    assert body["period"] == "monthly"
    assert body["category_code"] is None
    assert body["target_amount"] == "1500000.00"
    assert body["is_active"] is True
    assert "starts_on" in body


async def test_submitting_twice_returns_409(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    token = await _register_and_login(client, unique)
    headers = _auth_headers(token)
    first = await client.post(
        "/api/v1/onboarding/budget", json={"monthly_budget": "1000000"}, headers=headers
    )
    assert first.status_code == 201, first.text

    second = await client.post(
        "/api/v1/onboarding/budget", json={"monthly_budget": "2000000"}, headers=headers
    )
    assert second.status_code == 409


async def test_zero_budget_returns_422(client: AsyncClient, unique: Callable[[str], str]) -> None:
    token = await _register_and_login(client, unique)
    resp = await client.post(
        "/api/v1/onboarding/budget", json={"monthly_budget": "0"}, headers=_auth_headers(token)
    )
    assert resp.status_code == 422


async def test_negative_budget_returns_422(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    token = await _register_and_login(client, unique)
    resp = await client.post(
        "/api/v1/onboarding/budget", json={"monthly_budget": "-500"}, headers=_auth_headers(token)
    )
    assert resp.status_code == 422


async def test_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/onboarding/budget", json={"monthly_budget": "1000000"})
    assert resp.status_code == 401


async def test_me_404s_before_submission_and_returns_it_after(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    token = await _register_and_login(client, unique)
    headers = _auth_headers(token)

    before = await client.get("/api/v1/onboarding/budget/me", headers=headers)
    assert before.status_code == 404

    submit = await client.post(
        "/api/v1/onboarding/budget", json={"monthly_budget": "1000000"}, headers=headers
    )
    assert submit.status_code == 201, submit.text

    after = await client.get("/api/v1/onboarding/budget/me", headers=headers)
    assert after.status_code == 200
    assert after.json()["id"] == submit.json()["id"]


async def test_me_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/onboarding/budget/me")
    assert resp.status_code == 401
