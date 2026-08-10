"""Per-user physiological baseline computation.

Arousal-scoring domain. Nothing here may import from wellness.models.transactions,
wellness.models.financial, wellness.models.banking, or wellness.models.goals —
see the boundary comment at the top of wellness.models.transactions. Arousal is
computed from physiology alone; spending data plays no role.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.models.baseline import UserBaseline
from wellness.models.biometric_samples import BiometricSample
from wellness.models.checkins import Checkin

# Matches the metric names documented on UserBaseline.metric.
METRICS = ("heart_rate", "hrv_ms", "eda_microsiemens", "spo2_percent", "skin_temp_c")

# Metrics biometric_samples can supply. eda_microsiemens and skin_temp_c have
# no wearable equivalent and always come from checkins.
_SAMPLE_METRICS = ("heart_rate", "hrv_ms", "spo2_percent")

# Minimum non-null samples for a metric before samples replace checkins as
# the baseline source for it.
SAMPLE_SOURCE_MIN_N = 30


async def refresh_baseline(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Recompute this user's baseline for every metric with at least one
    non-null reading, from scratch. For heart_rate, hrv_ms and spo2_percent,
    biometric_samples is used once the user has at least SAMPLE_SOURCE_MIN_N
    non-null samples for that metric; otherwise (and always for
    eda_microsiemens/skin_temp_c) checkins is used. Metrics with zero
    non-null readings from their source are left untouched (no row written).
    """
    for metric in METRICS:
        source = "checkins"
        column = getattr(Checkin, metric)
        filters = (Checkin.user_id == user_id, column.is_not(None))

        if metric in _SAMPLE_METRICS:
            sample_column = getattr(BiometricSample, metric)
            sample_count = (
                await session.execute(
                    select(func.count(sample_column)).where(
                        BiometricSample.user_id == user_id, sample_column.is_not(None)
                    )
                )
            ).scalar_one()
            if sample_count >= SAMPLE_SOURCE_MIN_N:
                source = "samples"
                column = sample_column
                filters = (BiometricSample.user_id == user_id, column.is_not(None))

        mean_value, sd_value, sample_n, min_value, max_value = (
            await session.execute(
                select(
                    func.avg(column),
                    func.stddev_samp(column),
                    func.count(column),
                    func.min(column),
                    func.max(column),
                ).where(*filters)
            )
        ).one()

        if sample_n == 0:
            continue

        stmt = insert(UserBaseline).values(
            user_id=user_id,
            metric=metric,
            mean_value=mean_value,
            sd_value=sd_value,
            sample_n=sample_n,
            min_value=min_value,
            max_value=max_value,
            source=source,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[UserBaseline.user_id, UserBaseline.metric],
            set_={
                "mean_value": stmt.excluded.mean_value,
                "sd_value": stmt.excluded.sd_value,
                "sample_n": stmt.excluded.sample_n,
                "min_value": stmt.excluded.min_value,
                "max_value": stmt.excluded.max_value,
                "source": stmt.excluded.source,
                "computed_at": func.now(),
            },
        )
        await session.execute(stmt)

    await session.commit()
