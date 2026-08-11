"""Integration tests for wiring biometric_samples into the baseline and
arousal-scoring services (wellness/services/baseline.py,
wellness/services/arousal.py). Exercised through the real HTTP API, same
approach as test_arousal_scoring.py: POST /checkins triggers
refresh_baseline() then score_checkin(), and biometric samples are seeded
through POST /api/v1/samples/batch (still unauthenticated — takes user_id
directly — see the TODO in samples.py). Everything else here (checkins,
arousal, user-baseline) requires the matching auth headers.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response

# A ten-value spread with real variance, reused wherever a plain
# checkins-sourced baseline is needed (mirrors test_arousal_scoring.py).
_TEN_HR_VALUES = (68, 74, 71, 80, 65, 90, 72, 69, 77, 83)


def _cycle(values: tuple[float, ...], n: int) -> list[float]:
    return [values[i % len(values)] for i in range(n)]


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


async def _post_samples(
    client: AsyncClient,
    user_id: str,
    metric: str,
    readings: list[tuple[datetime, float]],
) -> None:
    payload = [{"user_id": user_id, "ts": ts.isoformat(), metric: value} for ts, value in readings]
    resp = await client.post("/api/v1/samples/batch", json=payload)
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["inserted"] == len(readings), result


def _minutes_ago(n: float, *, now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return now - timedelta(minutes=n)


async def test_user_with_200_samples_and_2_checkins_gets_source_samples(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    user_id, headers = authed_user
    now = datetime.now(UTC)
    # All well outside the 15-minute pre-checkin window, so this only
    # exercises baseline source selection, not window reading resolution.
    readings = [
        (_minutes_ago(30 + i, now=now), v) for i, v in enumerate(_cycle(_TEN_HR_VALUES, 200))
    ]
    await _post_samples(client, user_id, "heart_rate", readings)

    await _create_checkin(client, headers, heart_rate=75)
    checkin2 = await _create_checkin(client, headers, heart_rate=80)

    baseline_resp = await client.get("/api/v1/user-baseline/heart_rate", headers=headers)
    assert baseline_resp.status_code == 200
    baseline = baseline_resp.json()
    assert baseline["source"] == "samples"
    assert baseline["sample_n"] == 200

    arousal = (await _get_arousal(client, checkin2["id"], headers)).json()
    assert arousal["label"] != "unknown"


async def test_user_with_0_samples_scores_from_checkins_exactly_as_before(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    _user_id, headers = authed_user
    checkin = {}
    for hr in _TEN_HR_VALUES:
        checkin = await _create_checkin(client, headers, heart_rate=hr)

    arousal = (await _get_arousal(client, checkin["id"], headers)).json()
    assert arousal["z_heart_rate"] is not None
    assert arousal["label"] != "unknown"
    assert arousal["reading_source"] == "checkins"
    assert arousal["window_sample_count"] == 0

    baseline_resp = await client.get("/api/v1/user-baseline/heart_rate", headers=headers)
    baseline = baseline_resp.json()
    assert baseline["source"] == "checkins"


async def test_window_average_used_when_at_least_3_samples_in_window(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    user_id, headers = authed_user
    for hr in _TEN_HR_VALUES:
        await _create_checkin(client, headers, heart_rate=hr)

    now = datetime.now(UTC)
    readings = [(_minutes_ago(m, now=now), 150.0) for m in (1, 2, 3)]
    await _post_samples(client, user_id, "heart_rate", readings)

    # Typed value (70) is close to the checkins baseline mean (~75); the
    # window average (150) is far above it, so which one gets used is
    # unambiguous from the resulting z-score.
    spike = await _create_checkin(client, headers, heart_rate=70)
    arousal = (await _get_arousal(client, spike["id"], headers)).json()

    assert arousal["reading_source"] == "samples"
    assert arousal["window_sample_count"] == 3
    assert arousal["z_heart_rate"] > 2


async def test_fewer_than_3_samples_in_window_falls_back_to_typed_checkin_value(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    user_id, headers = authed_user
    for hr in _TEN_HR_VALUES:
        await _create_checkin(client, headers, heart_rate=hr)

    now = datetime.now(UTC)
    readings = [(_minutes_ago(m, now=now), 150.0) for m in (1, 2)]
    await _post_samples(client, user_id, "heart_rate", readings)

    checkin = await _create_checkin(client, headers, heart_rate=70)
    arousal = (await _get_arousal(client, checkin["id"], headers)).json()

    assert arousal["reading_source"] == "checkins"
    assert arousal["window_sample_count"] == 0
    assert arousal["z_heart_rate"] is not None
    assert abs(arousal["z_heart_rate"]) < 2


async def test_sign_elevated_heart_rate_samples_sourced_raises_score_above_half(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    user_id, headers = authed_user
    now = datetime.now(UTC)
    baseline_readings = [
        (_minutes_ago(60 + i, now=now), v)
        for i, v in enumerate(_cycle((65, 68, 70, 72, 74, 76, 78, 80, 82, 85), 40))
    ]
    await _post_samples(client, user_id, "heart_rate", baseline_readings)
    await _create_checkin(client, headers, heart_rate=75)  # triggers refresh_baseline

    baseline_resp = await client.get("/api/v1/user-baseline/heart_rate", headers=headers)
    assert baseline_resp.json()["source"] == "samples"

    spike_readings = [(_minutes_ago(m, now=now), 190.0) for m in (1, 2, 3)]
    await _post_samples(client, user_id, "heart_rate", spike_readings)

    spike = await _create_checkin(client, headers, heart_rate=75)
    arousal = (await _get_arousal(client, spike["id"], headers)).json()

    assert arousal["reading_source"] == "samples"
    assert arousal["z_heart_rate"] > 0
    assert arousal["score"] > 0.5


async def test_sign_elevated_hrv_samples_sourced_lowers_score_below_half(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    user_id, headers = authed_user
    now = datetime.now(UTC)
    baseline_readings = [
        (_minutes_ago(60 + i, now=now), v)
        for i, v in enumerate(_cycle((45, 47, 49, 51, 53, 55, 57, 59, 61, 63), 40))
    ]
    await _post_samples(client, user_id, "hrv_ms", baseline_readings)
    await _create_checkin(client, headers, hrv_ms=51)  # triggers refresh_baseline

    baseline_resp = await client.get("/api/v1/user-baseline/hrv_ms", headers=headers)
    assert baseline_resp.json()["source"] == "samples"

    spike_readings = [(_minutes_ago(m, now=now), 200.0) for m in (1, 2, 3)]
    await _post_samples(client, user_id, "hrv_ms", spike_readings)

    spike = await _create_checkin(client, headers, hrv_ms=51)
    arousal = (await _get_arousal(client, spike["id"], headers)).json()

    assert arousal["reading_source"] == "samples"
    assert arousal["z_hrv"] > 0
    assert arousal["score"] < 0.5


async def test_baseline_factor_1_0_for_samples_source_with_100_or_more_samples(
    client: AsyncClient, authed_user: tuple[str, dict[str, str]]
) -> None:
    user_id, headers = authed_user
    now = datetime.now(UTC)
    readings = [
        (_minutes_ago(30 + i, now=now), v) for i, v in enumerate(_cycle(_TEN_HR_VALUES, 120))
    ]
    await _post_samples(client, user_id, "heart_rate", readings)

    checkin = await _create_checkin(client, headers, heart_rate=75)
    arousal = (await _get_arousal(client, checkin["id"], headers)).json()

    # metrics_used=1, baseline_factor=1.0 (samples, n>=100) -> confidence=0.2
    assert arousal["metrics_used"] == 1
    assert arousal["confidence"] == pytest.approx(0.2)
