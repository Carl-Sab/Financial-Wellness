"""Integration tests for login/refresh/logout/me — the session half of JWT
auth. Registration is covered separately in test_auth_register.py; these
tests register a user as setup, then exercise the actual session lifecycle:
issuing tokens, rotating refresh tokens, detecting reuse, revoking on
logout, and rate-limiting repeated failures.
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt as pyjwt
from httpx import AsyncClient, Response

from wellness.config import get_settings
from wellness.security import JWT_ALGORITHM

PASSWORD = "hunter2pass"


async def _register(client: AsyncClient, unique: Callable[[str], str]) -> str:
    email = f"{unique('login')}@example.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Ada Lovelace",
            "email": email,
            "password": PASSWORD,
            "date_of_birth": "1990-01-01",
        },
    )
    assert resp.status_code == 201, resp.text
    return email


def _set_cookie_header(resp: Response) -> str:
    header: str = resp.headers.get("set-cookie", "")
    assert header, "expected a Set-Cookie header"
    return header


def _refresh_cookie(token: str) -> dict[str, str]:
    # A raw Cookie header, not httpx's per-request cookies= kwarg: several
    # tests need to present a *specific* historical token value (the one
    # already-rotated-out, a sibling from the same family, ...) rather than
    # whatever the client's own cookie jar currently holds, and httpx's
    # per-request cookies= is being deprecated for exactly that ambiguity.
    return {"Cookie": f"refresh_token={token}"}


async def test_login_returns_access_token_and_sets_refresh_cookie(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    email = await _register(client, unique)

    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]

    cookie_header = _set_cookie_header(resp)
    assert "refresh_token=" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "samesite=lax" in cookie_header.lower()
    assert "Path=/api/v1/auth" in cookie_header
    # environment=local in the test .env — Secure must NOT be set, or the
    # cookie would never be sent back over plain-HTTP localhost.
    assert get_settings().environment == "local"
    assert "Secure" not in cookie_header


async def test_wrong_password_401s_and_does_not_reveal_account_existence(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    email = await _register(client, unique)

    wrong_password_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "wrongpassword1"}
    )
    no_such_account_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": f"{unique('ghost')}@example.com", "password": "wrongpassword1"},
    )

    assert wrong_password_resp.status_code == 401
    assert no_such_account_resp.status_code == 401
    assert wrong_password_resp.json()["detail"] == no_such_account_resp.json()["detail"]
    assert "exist" not in wrong_password_resp.json()["detail"].lower()


async def test_expired_access_token_401s(client: AsyncClient, unique: Callable[[str], str]) -> None:
    email = await _register(client, unique)
    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )

    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login_resp.json()['access_token']}"},
    )
    assert me_resp.status_code == 200

    expired_token = pyjwt.encode(
        {
            "sub": me_resp.json()["id"],
            "iat": datetime.now(UTC) - timedelta(minutes=30),
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        get_settings().jwt_secret,
        algorithm=JWT_ALGORITHM,
    )
    expired_resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert expired_resp.status_code == 401


async def test_me_without_token_401s(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_refresh_rotates_and_old_token_stops_working(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    email = await _register(client, unique)
    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    old_refresh_token = login_resp.cookies["refresh_token"]

    refresh_resp = await client.post("/api/v1/auth/refresh")
    assert refresh_resp.status_code == 200, refresh_resp.text
    new_access_token = refresh_resp.json()["access_token"]
    # Not "!= the login one": a JWT is a deterministic function of its
    # claims, and login+refresh here happen within the same second, so
    # identical claims can legitimately produce an identical token. What
    # actually matters is that the new token is valid.
    me_resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {new_access_token}"}
    )
    assert me_resp.status_code == 200

    new_refresh_token = refresh_resp.cookies["refresh_token"]
    assert new_refresh_token != old_refresh_token

    # The rotated-out token must no longer work.
    replay_resp = await client.post(
        "/api/v1/auth/refresh", headers=_refresh_cookie(old_refresh_token)
    )
    assert replay_resp.status_code == 401


async def test_reuse_of_rotated_token_revokes_whole_family(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    email = await _register(client, unique)
    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    token_a = login_resp.cookies["refresh_token"]

    # Legitimate rotation: A -> B.
    refresh_resp = await client.post(
        "/api/v1/auth/refresh", headers=_refresh_cookie(token_a)
    )
    assert refresh_resp.status_code == 200, refresh_resp.text
    token_b = refresh_resp.cookies["refresh_token"]
    assert token_b != token_a

    # Reuse A: proof of theft, should revoke the whole family (including B).
    reuse_resp = await client.post(
        "/api/v1/auth/refresh", headers=_refresh_cookie(token_a)
    )
    assert reuse_resp.status_code == 401

    # B — A's legitimate successor, otherwise still unexpired and unused —
    # must now also be dead, because reuse revoked the entire family.
    sibling_resp = await client.post(
        "/api/v1/auth/refresh", headers=_refresh_cookie(token_b)
    )
    assert sibling_resp.status_code == 401


async def test_logout_revokes_and_subsequent_refresh_401s(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    email = await _register(client, unique)
    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    refresh_token = login_resp.cookies["refresh_token"]

    logout_resp = await client.post(
        "/api/v1/auth/logout", headers=_refresh_cookie(refresh_token)
    )
    assert logout_resp.status_code == 204

    # The cookie the logout response sends back should be an empty/expired
    # clear, not a live token.
    cleared_header = logout_resp.headers.get("set-cookie", "")
    assert 'refresh_token=""' in cleared_header or "refresh_token=;" in cleared_header

    after_logout_resp = await client.post(
        "/api/v1/auth/refresh", headers=_refresh_cookie(refresh_token)
    )
    assert after_logout_resp.status_code == 401


async def test_logout_without_a_cookie_is_a_no_op_success(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 204


async def test_refresh_without_a_cookie_401s(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


async def test_refresh_with_garbage_cookie_401s(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/refresh", headers=_refresh_cookie("not-a-real-token")
    )
    assert resp.status_code == 401


async def test_rate_limit_triggers_on_sixth_failed_attempt(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    email = await _register(client, unique)

    statuses = []
    for _ in range(6):
        resp = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "wrongpassword1"}
        )
        statuses.append(resp.status_code)

    assert statuses[:5] == [401, 401, 401, 401, 401]
    assert statuses[5] == 429

    # Rate limiting must hold even with the CORRECT password now — five
    # failures have already used up the window, so the account is locked
    # out of its own correct credentials until the window passes.
    correct_password_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert correct_password_resp.status_code == 429


async def test_rate_limit_is_keyed_per_email_not_global(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    victim_email = await _register(client, unique)
    for _ in range(5):
        await client.post(
            "/api/v1/auth/login", json={"email": victim_email, "password": "wrongpassword1"}
        )

    other_email = await _register(client, unique)
    resp = await client.post(
        "/api/v1/auth/login", json={"email": other_email, "password": PASSWORD}
    )
    assert resp.status_code == 200, resp.text


async def test_full_session_lifecycle_end_to_end(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    """register -> login -> me -> refresh -> me with new token -> logout."""
    email = await _register(client, unique)

    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    access_token = login_resp.json()["access_token"]

    me_resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"].lower() == email.lower()
    assert uuid.UUID(me_resp.json()["id"])  # well-formed UUID

    refresh_resp = await client.post("/api/v1/auth/refresh")
    assert refresh_resp.status_code == 200
    new_access_token = refresh_resp.json()["access_token"]

    me_again_resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {new_access_token}"}
    )
    assert me_again_resp.status_code == 200

    logout_resp = await client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 204

    # The access token itself is still technically valid until it expires —
    # logout only revokes the refresh chain, not already-issued JWTs. That's
    # the documented tradeoff of stateless access tokens (see security.py).
    still_works_resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {new_access_token}"}
    )
    assert still_works_resp.status_code == 200
