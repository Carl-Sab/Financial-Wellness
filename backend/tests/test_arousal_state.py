"""Integration tests for /api/v1/arousal-state — distinct from
GET /checkins/{id}/arousal (checkins.py), which is exercised in
test_arousal_scoring.py. This router is the standalone list/get surface
over the same rows.
"""

from collections.abc import Awaitable, Callable

from httpx import AsyncClient


async def _create_scored_checkin(client: AsyncClient, headers: dict[str, str]) -> int:
    """A checkin with a reading, scored via the real POST /checkins path —
    returns the resulting arousal_state's id."""
    checkin_resp = await client.post(
        "/api/v1/checkins",
        json={"category_code": "groceries", "valence": "neutral", "heart_rate": 80},
        headers=headers,
    )
    assert checkin_resp.status_code == 201, checkin_resp.text
    checkin_id = checkin_resp.json()["id"]

    arousal_resp = await client.get(f"/api/v1/checkins/{checkin_id}/arousal", headers=headers)
    assert arousal_resp.status_code == 200, arousal_resp.text
    state_id: int = arousal_resp.json()["id"]
    return state_id


async def test_get_and_list_arousal_state(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    user_id, headers = authed_user
    state_id = await _create_scored_checkin(client, headers)

    get_resp = await client.get(f"/api/v1/arousal-state/{state_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["user_id"] == user_id

    list_resp = await client.get("/api/v1/arousal-state", headers=headers)
    assert list_resp.status_code == 200
    assert any(s["id"] == state_id for s in list_resp.json())


async def test_list_arousal_state_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/arousal-state")
    assert resp.status_code == 401


async def test_get_arousal_state_unauthenticated_returns_401(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    state_id = await _create_scored_checkin(client, headers)

    resp = await client.get(f"/api/v1/arousal-state/{state_id}")
    assert resp.status_code == 401


async def test_user_b_cannot_read_user_a_arousal_state(
    client: AsyncClient,
    make_authed_user: Callable[[], Awaitable[tuple[str, dict[str, str]]]],
) -> None:
    _user_a, headers_a = await make_authed_user()
    _user_b, headers_b = await make_authed_user()

    state_id = await _create_scored_checkin(client, headers_a)

    get_resp = await client.get(f"/api/v1/arousal-state/{state_id}", headers=headers_b)
    assert get_resp.status_code == 404


async def test_list_arousal_state_only_returns_the_authenticated_users_own(
    client: AsyncClient,
    make_authed_user: Callable[[], Awaitable[tuple[str, dict[str, str]]]],
) -> None:
    _user_a, headers_a = await make_authed_user()
    _user_b, headers_b = await make_authed_user()

    await _create_scored_checkin(client, headers_a)

    b_states = (await client.get("/api/v1/arousal-state", headers=headers_b)).json()
    assert b_states == []
