from httpx import AsyncClient

from wellness.services.prediction import overspending_risk_level


async def _complete_prediction_prerequisites(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    questionnaire = await client.post(
        "/api/v1/questionnaire-responses",
        headers=headers,
        json={
            "impulse_tendency_score": 2.7,
            "self_control_score": 3.0,
            "hedonic_score": 4.6,
            "utilitarian_score": 4.3,
            "normative_eval_score": 3.0,
            "raw_responses": {},
        },
    )
    assert questionnaire.status_code == 201, questionnaire.text

    budget = await client.post(
        "/api/v1/onboarding/budget",
        headers=headers,
        json={"monthly_budget": "3000000", "currency": "LBP"},
    )
    assert budget.status_code == 201, budget.text


def test_probability_display_bands_use_exact_product_thresholds() -> None:
    assert overspending_risk_level(0.329999) == "low"
    assert overspending_risk_level(0.33) == "medium"
    assert overspending_risk_level(0.66) == "medium"
    assert overspending_risk_level(0.660001) == "high"


async def test_manual_arousal_bypasses_case_and_returns_live_prediction(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    await _complete_prediction_prerequisites(client, headers)
    checkin = await client.post(
        "/api/v1/checkins",
        headers=headers,
        json={
            "category_code": "groceries",
            "valence": "pleasant",
            "arousal_input_mode": "manual",
            "arousal_z": -1,
        },
    )
    assert checkin.status_code == 201, checkin.text

    response = await client.post(
        f"/api/v1/checkins/{checkin.json()['id']}/prediction", headers=headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["arousal_input_mode"] == "manual"
    assert body["arousal_z"] == -1
    assert body["arousal_case_score"] is None
    assert 0 <= body["overspending_probability"] <= 1
    assert body["overspending_percentage"] == round(
        body["overspending_probability"] * 100
    )
    assert body["risk_level"] in {"low", "medium", "high"}


async def test_detailed_arousal_runs_case_before_prediction(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    await _complete_prediction_prerequisites(client, headers)
    checkin = await client.post(
        "/api/v1/checkins",
        headers=headers,
        json={
            "category_code": "online",
            "valence": "neutral",
            "arousal_input_mode": "detailed",
            "perceived_heart_rate": 2,
            "perceived_heartbeat_steadiness": -1,
            "perceived_sweating": 1,
            "perceived_respiration": 0,
            "perceived_temperature_difference": -2,
        },
    )
    assert checkin.status_code == 201, checkin.text

    response = await client.post(
        f"/api/v1/checkins/{checkin.json()['id']}/prediction", headers=headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["arousal_input_mode"] == "detailed"
    assert body["arousal_case_score"] is not None
    assert isinstance(body["arousal_z"], float)


async def test_prediction_requires_a_budget(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    questionnaire = await client.post(
        "/api/v1/questionnaire-responses",
        headers=headers,
        json={
            "impulse_tendency_score": 2.7,
            "self_control_score": 3.0,
            "hedonic_score": 4.6,
            "utilitarian_score": 4.3,
            "normative_eval_score": 3.0,
            "raw_responses": {},
        },
    )
    assert questionnaire.status_code == 201
    checkin = await client.post(
        "/api/v1/checkins",
        headers=headers,
        json={
            "category_code": "groceries",
            "valence": "neutral",
            "arousal_input_mode": "manual",
            "arousal_z": 0,
        },
    )

    response = await client.post(
        f"/api/v1/checkins/{checkin.json()['id']}/prediction", headers=headers
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Set a monthly budget first"
