from collections.abc import Awaitable, Callable

from httpx import AsyncClient


async def test_checkin_crud_lifecycle(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    create_resp = await client.post(
        "/api/v1/checkins",
        json={"category_code": "groceries", "valence": "neutral", "heart_rate": 80},
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    checkin = create_resp.json()
    assert checkin["valence"] == "neutral"
    checkin_id = checkin["id"]

    get_resp = await client.get(f"/api/v1/checkins/{checkin_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["heart_rate"] == 80.0

    patch_resp = await client.patch(
        f"/api/v1/checkins/{checkin_id}", json={"heart_rate": 90}, headers=headers
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["heart_rate"] == 90.0

    delete_resp = await client.delete(f"/api/v1/checkins/{checkin_id}", headers=headers)
    assert delete_resp.status_code == 204

    missing_resp = await client.get(f"/api/v1/checkins/{checkin_id}", headers=headers)
    assert missing_resp.status_code == 404


async def test_checkin_requires_at_least_one_reading(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    resp = await client.post(
        "/api/v1/checkins",
        json={"category_code": "groceries", "valence": "neutral"},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_create_checkin_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/checkins",
        json={"category_code": "groceries", "valence": "neutral", "heart_rate": 80},
    )
    assert resp.status_code == 401


async def test_list_checkins_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/checkins")
    assert resp.status_code == 401


async def test_created_checkin_belongs_to_the_authenticated_user(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    user_id, headers = authed_user
    create_resp = await client.post(
        "/api/v1/checkins",
        json={"category_code": "groceries", "valence": "neutral", "heart_rate": 80},
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    assert create_resp.json()["user_id"] == user_id


async def test_user_b_cannot_read_user_a_checkin(
    client: AsyncClient,
    make_authed_user: Callable[[], Awaitable[tuple[str, dict[str, str]]]],
) -> None:
    _user_a, headers_a = await make_authed_user()
    _user_b, headers_b = await make_authed_user()

    create_resp = await client.post(
        "/api/v1/checkins",
        json={"category_code": "groceries", "valence": "neutral", "heart_rate": 80},
        headers=headers_a,
    )
    checkin_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/checkins/{checkin_id}", headers=headers_b)
    assert get_resp.status_code == 404

    arousal_resp = await client.get(f"/api/v1/checkins/{checkin_id}/arousal", headers=headers_b)
    assert arousal_resp.status_code == 404

    patch_resp = await client.patch(
        f"/api/v1/checkins/{checkin_id}", json={"heart_rate": 200}, headers=headers_b
    )
    assert patch_resp.status_code == 404

    delete_resp = await client.delete(f"/api/v1/checkins/{checkin_id}", headers=headers_b)
    assert delete_resp.status_code == 404

    still_there = await client.get(f"/api/v1/checkins/{checkin_id}", headers=headers_a)
    assert still_there.status_code == 200


async def test_list_checkins_only_returns_the_authenticated_users_own(
    client: AsyncClient,
    make_authed_user: Callable[[], Awaitable[tuple[str, dict[str, str]]]],
) -> None:
    _user_a, headers_a = await make_authed_user()
    _user_b, headers_b = await make_authed_user()

    await client.post(
        "/api/v1/checkins",
        json={"category_code": "groceries", "valence": "neutral", "heart_rate": 80},
        headers=headers_a,
    )

    b_checkins = (await client.get("/api/v1/checkins", headers=headers_b)).json()
    assert b_checkins == []
