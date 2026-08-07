"""Integration tests for /api/v1/samples."""

from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient


async def test_create_sample(client: AsyncClient, user_id: str) -> None:
    resp = await client.post(
        "/api/v1/samples",
        json={"user_id": user_id, "ts": "2026-01-01T08:00:00Z", "heart_rate": 72},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["heart_rate"] == 72.0
    assert body["data_source"] == "healthkit"


async def test_duplicate_sample_is_silently_ignored_not_409(
    client: AsyncClient, user_id: str
) -> None:
    payload: dict[str, Any] = {
        "user_id": user_id,
        "ts": "2026-01-02T08:00:00Z",
        "heart_rate": 65,
    }

    first = await client.post("/api/v1/samples", json=payload)
    assert first.status_code == 201
    first_id = first.json()["id"]

    # Same (user_id, ts, data_source), different heart_rate — the duplicate
    # key wins the silent-ignore, the new heart_rate is simply dropped.
    second = await client.post("/api/v1/samples", json={**payload, "heart_rate": 99})
    assert second.status_code == 200
    assert second.json()["id"] == first_id
    assert second.json()["heart_rate"] == 65.0

    list_resp = await client.get("/api/v1/samples", params={"limit": 200})
    matching = [s for s in list_resp.json() if s["id"] == first_id]
    assert len(matching) == 1


async def test_all_null_readings_rejected(client: AsyncClient, user_id: str) -> None:
    resp = await client.post(
        "/api/v1/samples", json={"user_id": user_id, "ts": "2026-01-01T08:00:00Z"}
    )
    assert resp.status_code == 422


async def test_batch_reports_inserted_and_skipped_on_partial_duplicates(
    client: AsyncClient, user_id: str
) -> None:
    base = [
        {"user_id": user_id, "ts": f"2026-01-03T0{h}:00:00Z", "heart_rate": 60 + h}
        for h in range(5)
    ]
    first_batch = await client.post("/api/v1/samples/batch", json=base)
    assert first_batch.status_code == 200
    assert first_batch.json() == {"received": 5, "inserted": 5, "skipped": 0}

    # 3 of these repeat the first batch's (user_id, ts) exactly; 2 are new.
    second_batch_payload = [
        *base[:3],
        {"user_id": user_id, "ts": "2026-01-03T10:00:00Z", "heart_rate": 70},
        {"user_id": user_id, "ts": "2026-01-03T11:00:00Z", "heart_rate": 71},
    ]
    second_batch = await client.post("/api/v1/samples/batch", json=second_batch_payload)
    assert second_batch.status_code == 200
    assert second_batch.json() == {"received": 5, "inserted": 2, "skipped": 3}


async def test_batch_rejects_over_500(client: AsyncClient, user_id: str) -> None:
    base_ts = datetime(2026, 2, 1, tzinfo=UTC)
    too_many = [
        {
            "user_id": user_id,
            "ts": (base_ts + timedelta(seconds=i)).isoformat(),
            "heart_rate": 70,
        }
        for i in range(501)
    ]
    resp = await client.post("/api/v1/samples/batch", json=too_many)
    assert resp.status_code == 422


async def test_averages_group_correctly_across_a_day_boundary(
    client: AsyncClient, user_id: str
) -> None:
    late_jan1 = await client.post(
        "/api/v1/samples",
        json={"user_id": user_id, "ts": "2026-04-01T23:30:00Z", "heart_rate": 60},
    )
    assert late_jan1.status_code == 201
    early_jan2 = await client.post(
        "/api/v1/samples",
        json={"user_id": user_id, "ts": "2026-04-02T00:30:00Z", "heart_rate": 80},
    )
    assert early_jan2.status_code == 201

    resp = await client.get(
        "/api/v1/samples/averages",
        params={
            "user_id": user_id,
            "period": "day",
            "from_date": "2026-04-01",
            "to_date": "2026-04-02",
        },
    )
    assert resp.status_code == 200
    buckets = resp.json()
    assert len(buckets) == 2

    bucket_by_date = {b["period_start"][:10]: b for b in buckets}
    assert bucket_by_date["2026-04-01"]["avg_heart_rate"] == 60.0
    assert bucket_by_date["2026-04-01"]["count"] == 1
    assert bucket_by_date["2026-04-02"]["avg_heart_rate"] == 80.0
    assert bucket_by_date["2026-04-02"]["count"] == 1


async def test_get_and_delete_sample(client: AsyncClient, user_id: str) -> None:
    create_resp = await client.post(
        "/api/v1/samples",
        json={"user_id": user_id, "ts": "2026-01-05T08:00:00Z", "heart_rate": 70},
    )
    sample_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/samples/{sample_id}")
    assert get_resp.status_code == 200

    delete_resp = await client.delete(f"/api/v1/samples/{sample_id}")
    assert delete_resp.status_code == 204

    missing_resp = await client.get(f"/api/v1/samples/{sample_id}")
    assert missing_resp.status_code == 404
