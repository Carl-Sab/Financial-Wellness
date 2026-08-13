from collections.abc import Awaitable, Callable

from httpx import AsyncClient


async def test_checkin_crud_lifecycle(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    create_resp = await client.post(
        "/api/v1/checkins",
        json={
            "category_code": "groceries",
            "valence": "neutral",
            "arousal_input_mode": "manual",
            "arousal_z": 0,
        },
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    checkin = create_resp.json()
    assert checkin["valence"] == "neutral"
    checkin_id = checkin["id"]

    get_resp = await client.get(f"/api/v1/checkins/{checkin_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["arousal_z"] == 0

    patch_resp = await client.patch(
        f"/api/v1/checkins/{checkin_id}", json={"valence": "pleasant"}, headers=headers
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["valence"] == "pleasant"

    delete_resp = await client.delete(f"/api/v1/checkins/{checkin_id}", headers=headers)
    assert delete_resp.status_code == 204

    missing_resp = await client.get(f"/api/v1/checkins/{checkin_id}", headers=headers)
    assert missing_resp.status_code == 404


async def test_checkin_requires_an_arousal_input_mode(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    resp = await client.post(
        "/api/v1/checkins",
        json={"category_code": "groceries", "valence": "neutral"},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_create_manual_arousal_checkin_stores_direct_discrete_value(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    resp = await client.post(
        "/api/v1/checkins",
        json={
            "category_code": "groceries",
            "valence": "neutral",
            "arousal_input_mode": "manual",
            "arousal_z": -1,
        },
        headers=headers,
    )

    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["arousal_input_mode"] == "manual"
    assert created["arousal_z"] == -1
    assert created["perceived_heart_rate"] is None


async def test_create_detailed_arousal_checkin_stores_all_five_values(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    values = {
        "perceived_heart_rate": -2,
        "perceived_heartbeat_steadiness": -1,
        "perceived_sweating": 0,
        "perceived_respiration": 1,
        "perceived_temperature_difference": 2,
    }
    resp = await client.post(
        "/api/v1/checkins",
        json={
            "category_code": "groceries",
            "valence": "neutral",
            "arousal_input_mode": "detailed",
            **values,
        },
        headers=headers,
    )

    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["arousal_input_mode"] == "detailed"
    assert created["arousal_z"] is None
    assert {field: created[field] for field in values} == values


async def test_arousal_values_must_be_one_of_five_discrete_slider_stops(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    resp = await client.post(
        "/api/v1/checkins",
        json={
            "category_code": "groceries",
            "valence": "neutral",
            "arousal_input_mode": "manual",
            "arousal_z": 1.5,
        },
        headers=headers,
    )

    assert resp.status_code == 422


async def test_detailed_arousal_requires_all_five_values(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    resp = await client.post(
        "/api/v1/checkins",
        json={
            "category_code": "groceries",
            "valence": "neutral",
            "arousal_input_mode": "detailed",
            "perceived_heart_rate": 0,
        },
        headers=headers,
    )

    assert resp.status_code == 422


async def test_create_checkin_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/checkins",
        json={
            "category_code": "groceries",
            "valence": "neutral",
            "arousal_input_mode": "manual",
            "arousal_z": 0,
        },
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
        json={
            "category_code": "groceries",
            "valence": "neutral",
            "arousal_input_mode": "manual",
            "arousal_z": 0,
        },
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
        json={
            "category_code": "groceries",
            "valence": "neutral",
            "arousal_input_mode": "manual",
            "arousal_z": 0,
        },
        headers=headers_a,
    )
    checkin_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/checkins/{checkin_id}", headers=headers_b)
    assert get_resp.status_code == 404

    arousal_resp = await client.get(f"/api/v1/checkins/{checkin_id}/arousal", headers=headers_b)
    assert arousal_resp.status_code == 404

    patch_resp = await client.patch(
        f"/api/v1/checkins/{checkin_id}", json={"valence": "pleasant"}, headers=headers_b
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
        json={
            "category_code": "groceries",
            "valence": "neutral",
            "arousal_input_mode": "manual",
            "arousal_z": 0,
        },
        headers=headers_a,
    )

    b_checkins = (await client.get("/api/v1/checkins", headers=headers_b)).json()
    assert b_checkins == []
