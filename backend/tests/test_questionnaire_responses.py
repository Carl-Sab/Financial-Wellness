"""Smoke-test CRUD for /api/v1/questionnaire-responses — distinct from the
real, server-scored signup flow at POST /api/v1/questionnaire, covered in
test_questionnaire.py. This still accepts client-supplied scores; it's just
scoped to the caller now.
"""

from collections.abc import Awaitable, Callable

from httpx import AsyncClient

_PAYLOAD = {
    "impulse_tendency_score": 3.5,
    "self_control_score": 2.5,
    "hedonic_score": 4.0,
    "utilitarian_score": 5.0,
    "normative_eval_score": 3.0,
    "raw_responses": {"ibt_1": 4, "sc_1": 2},
}


async def test_questionnaire_response_crud_lifecycle(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    create_resp = await client.post(
        "/api/v1/questionnaire-responses", json=_PAYLOAD, headers=headers
    )
    assert create_resp.status_code == 201, create_resp.text
    response_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/questionnaire-responses/{response_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["raw_responses"] == {"ibt_1": 4, "sc_1": 2}

    patch_resp = await client.patch(
        f"/api/v1/questionnaire-responses/{response_id}",
        json={"instrument_version": "v2"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["instrument_version"] == "v2"

    delete_resp = await client.delete(
        f"/api/v1/questionnaire-responses/{response_id}", headers=headers
    )
    assert delete_resp.status_code == 204

    missing_resp = await client.get(
        f"/api/v1/questionnaire-responses/{response_id}", headers=headers
    )
    assert missing_resp.status_code == 404


async def test_create_questionnaire_response_unauthenticated_returns_401(
    client: AsyncClient,
) -> None:
    resp = await client.post("/api/v1/questionnaire-responses", json=_PAYLOAD)
    assert resp.status_code == 401


async def test_created_response_belongs_to_the_authenticated_user(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    user_id, headers = authed_user
    create_resp = await client.post(
        "/api/v1/questionnaire-responses", json=_PAYLOAD, headers=headers
    )
    assert create_resp.status_code == 201, create_resp.text
    assert create_resp.json()["user_id"] == user_id


async def test_user_b_cannot_read_user_a_questionnaire_response(
    client: AsyncClient,
    make_authed_user: Callable[[], Awaitable[tuple[str, dict[str, str]]]],
) -> None:
    _user_a, headers_a = await make_authed_user()
    _user_b, headers_b = await make_authed_user()

    create_resp = await client.post(
        "/api/v1/questionnaire-responses", json=_PAYLOAD, headers=headers_a
    )
    response_id = create_resp.json()["id"]

    get_resp = await client.get(
        f"/api/v1/questionnaire-responses/{response_id}", headers=headers_b
    )
    assert get_resp.status_code == 404

    patch_resp = await client.patch(
        f"/api/v1/questionnaire-responses/{response_id}",
        json={"instrument_version": "v2"},
        headers=headers_b,
    )
    assert patch_resp.status_code == 404

    delete_resp = await client.delete(
        f"/api/v1/questionnaire-responses/{response_id}", headers=headers_b
    )
    assert delete_resp.status_code == 404

    still_there = await client.get(
        f"/api/v1/questionnaire-responses/{response_id}", headers=headers_a
    )
    assert still_there.status_code == 200
