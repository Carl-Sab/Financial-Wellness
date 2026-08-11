"""Integration tests for /api/v1/user-baseline. The route addresses a
baseline by metric only now (GET /user-baseline/{metric}) — the user comes
from the auth token, not a path segment — see test_arousal_scoring.py and
test_arousal_biometric_samples.py for the full baseline-computation
behavior; these tests are about the endpoint's auth/ownership surface.
"""

from collections.abc import Awaitable, Callable

from httpx import AsyncClient


async def _create_checkin_with_baseline(client: AsyncClient, headers: dict[str, str]) -> None:
    """A single checkin is enough to produce a user_baseline row for
    heart_rate (sample_n=1, sd_value=None) — see test_arousal_scoring.py."""
    resp = await client.post(
        "/api/v1/checkins",
        json={"category_code": "groceries", "valence": "neutral", "heart_rate": 80},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text


async def test_get_and_list_user_baseline(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    user_id, headers = authed_user
    await _create_checkin_with_baseline(client, headers)

    get_resp = await client.get("/api/v1/user-baseline/heart_rate", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["user_id"] == user_id

    list_resp = await client.get("/api/v1/user-baseline", headers=headers)
    assert list_resp.status_code == 200
    assert any(b["metric"] == "heart_rate" for b in list_resp.json())


async def test_get_user_baseline_missing_metric_404s(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    resp = await client.get("/api/v1/user-baseline/eda_microsiemens", headers=headers)
    assert resp.status_code == 404


async def test_list_user_baseline_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/user-baseline")
    assert resp.status_code == 401


async def test_get_user_baseline_unauthenticated_returns_401(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    await _create_checkin_with_baseline(client, headers)

    resp = await client.get("/api/v1/user-baseline/heart_rate")
    assert resp.status_code == 401


async def test_user_b_cannot_read_user_a_baseline(
    client: AsyncClient,
    make_authed_user: Callable[[], Awaitable[tuple[str, dict[str, str]]]],
) -> None:
    """B asking for 'heart_rate' gets B's own (missing) baseline, never A's
    — there's no way for B to even address A's row, since the path only
    ever names a metric, not a user."""
    _user_a, headers_a = await make_authed_user()
    _user_b, headers_b = await make_authed_user()

    await _create_checkin_with_baseline(client, headers_a)

    b_resp = await client.get("/api/v1/user-baseline/heart_rate", headers=headers_b)
    assert b_resp.status_code == 404

    b_list = (await client.get("/api/v1/user-baseline", headers=headers_b)).json()
    assert b_list == []
