"""Seed ~200 plausible heart-rate biometric samples across the last 7 days
for a given user, so HR charts (GET /api/v1/samples/averages) can be built
and demoed without a real watch.

Usage:
    uv run python scripts/seed_biometric_samples.py <user_id>
"""

import argparse
import asyncio
import math
import random
import uuid
from datetime import UTC, datetime, timedelta

from wellness.db import get_session
from wellness.models import BiometricSample

TOTAL_SAMPLES = 200
DAYS = 7


def _plausible_heart_rate(hour_of_day: float) -> float:
    """Lower overnight, higher in the afternoon, plus noise — a rough diurnal
    curve, not a physiological model.
    """
    baseline = 62 + 18 * math.sin((hour_of_day - 6) / 24 * 2 * math.pi)
    return round(max(40.0, min(180.0, baseline + random.gauss(0, 4))), 1)


async def seed(user_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    samples = []
    for _ in range(TOTAL_SAMPLES):
        ts = now - timedelta(seconds=random.uniform(0, DAYS * 24 * 3600))
        samples.append(
            BiometricSample(
                user_id=user_id,
                ts=ts,
                heart_rate=_plausible_heart_rate(ts.hour + ts.minute / 60),
                data_source="healthkit",
            )
        )

    async for session in get_session():
        session.add_all(samples)
        await session.commit()
        print(
            f"Inserted {len(samples)} biometric samples for user {user_id} "
            f"across the last {DAYS} days."
        )
        break


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("user_id", type=uuid.UUID, help="Target user's UUID")
    args = parser.parse_args()
    asyncio.run(seed(args.user_id))


if __name__ == "__main__":
    main()
