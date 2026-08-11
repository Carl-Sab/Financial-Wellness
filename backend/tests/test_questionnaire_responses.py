from httpx import AsyncClient


async def test_questionnaire_response_crud_lifecycle(client: AsyncClient, user_id: str) -> None:
    create_resp = await client.post(
        "/api/v1/questionnaire-responses",
        json={
            "user_id": user_id,
            "impulse_tendency_score": 3.5,
            "self_control_score": 2.5,
            "hedonic_score": 4.0,
            "utilitarian_score": 5.0,
            "normative_eval_score": 3.0,
            "raw_responses": {"ibt_1": 4, "sc_1": 2},
        },
    )
    assert create_resp.status_code == 201
    response_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/questionnaire-responses/{response_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["raw_responses"] == {"ibt_1": 4, "sc_1": 2}

    patch_resp = await client.patch(
        f"/api/v1/questionnaire-responses/{response_id}", json={"instrument_version": "v2"}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["instrument_version"] == "v2"

    delete_resp = await client.delete(f"/api/v1/questionnaire-responses/{response_id}")
    assert delete_resp.status_code == 204

    missing_resp = await client.get(f"/api/v1/questionnaire-responses/{response_id}")
    assert missing_resp.status_code == 404
