"""Integration tests for the baseline + arousal-scoring services, exercised
through the real check-in flow: POST /checkins triggers refresh_baseline()
then score_checkin() (see wellness/api/v1/checkins.py), so these tests only
talk to the HTTP API and inspect the resulting arousal_state / user_baseline
rows — the same path a real client would use.
"""

from typing import Any

import pytest
from httpx import AsyncClient, Response


async def _create_checkin(
    client: AsyncClient, headers: dict[str, str], **fields: Any
) -> dict[str, Any]:
    payload = {"category_code": "groceries", "valence": "neutral", **fields}
    resp = await client.post("/api/v1/checkins", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    result: dict[str, Any] = resp.json()
    return result


async def _get_arousal(client: AsyncClient, checkin_id: int, headers: dict[str, str]) -> Response:
    return await client.get(f"/api/v1/checkins/{checkin_id}/arousal", headers=headers)


async def test_single_checkin_sd_is_null_and_label_unknown(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    checkin = await _create_checkin(client, headers, heart_rate=75)

    baseline_resp = await client.get("/api/v1/user-baseline/heart_rate", headers=headers)
    assert baseline_resp.status_code == 200
    baseline = baseline_resp.json()
    assert baseline["sample_n"] == 1
    assert baseline["sd_value"] is None

    arousal = (await _get_arousal(client, checkin["id"], headers)).json()
    assert arousal["label"] == "unknown"


async def test_three_checkins_still_unknown_thin_baseline(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    checkin = {}
    for hr in (68, 74, 71):
        checkin = await _create_checkin(client, headers, heart_rate=hr)

    arousal = (await _get_arousal(client, checkin["id"], headers)).json()
    # sd is computable at n=3 (>= 2), so the z-score exists...
    assert arousal["z_heart_rate"] is not None
    # ...but baseline_factor is still 0 below n=8, so the label stays unknown.
    assert arousal["label"] == "unknown"


async def test_ten_checkins_varied_hr_label_not_unknown(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    checkin = {}
    for hr in (68, 74, 71, 80, 65, 90, 72, 69, 77, 83):
        checkin = await _create_checkin(client, headers, heart_rate=hr)

    arousal = (await _get_arousal(client, checkin["id"], headers)).json()
    assert arousal["z_heart_rate"] is not None
    assert arousal["label"] != "unknown"


async def test_sign_elevated_heart_rate_raises_score_above_half(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    for hr in (68, 71, 70, 69, 72, 70, 68, 71, 69, 70):
        await _create_checkin(client, headers, heart_rate=hr)

    spike = await _create_checkin(client, headers, heart_rate=150)
    arousal = (await _get_arousal(client, spike["id"], headers)).json()

    assert arousal["z_heart_rate"] > 0
    assert arousal["score"] > 0.5


async def test_sign_elevated_hrv_lowers_score_below_half(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    for hrv in (50, 52, 48, 51, 49, 50, 52, 48, 51, 50):
        await _create_checkin(client, headers, hrv_ms=hrv)

    spike = await _create_checkin(client, headers, hrv_ms=200)
    arousal = (await _get_arousal(client, spike["id"], headers)).json()

    assert arousal["z_hrv"] > 0
    assert arousal["score"] < 0.5


async def test_identical_readings_skip_metric_no_divide_by_zero(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    checkin = {}
    for _ in range(5):
        checkin = await _create_checkin(client, headers, heart_rate=75)

    arousal_resp = await _get_arousal(client, checkin["id"], headers)
    assert arousal_resp.status_code == 200  # would have raised ZeroDivisionError otherwise
    arousal = arousal_resp.json()
    assert arousal["z_heart_rate"] is None
    assert arousal["metrics_used"] == 0
    assert arousal["score"] is None
    assert arousal["label"] == "unknown"


async def test_single_metric_checkin_has_metrics_used_one_and_low_confidence(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    for hr in (68, 74, 71, 80, 65, 90, 72, 69, 77, 83):
        await _create_checkin(client, headers, heart_rate=hr)

    checkin = await _create_checkin(client, headers, heart_rate=85)
    arousal = (await _get_arousal(client, checkin["id"], headers)).json()

    assert arousal["metrics_used"] == 1
    # 11 checkins by now -> 8 <= sample_n < 20 -> baseline_factor 0.5
    # confidence = 0.2 * 1 * 0.5
    assert arousal["confidence"] == pytest.approx(0.1)


async def test_arousal_404_when_no_checkin(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    resp = await _get_arousal(client, 99_999_999, headers)
    assert resp.status_code == 404
