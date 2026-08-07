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
from wellness.models.checkins import Checkin

# Matches the metric names documented on UserBaseline.metric.
METRICS = ("heart_rate", "hrv_ms", "eda_microsiemens", "spo2_percent", "skin_temp_c")


async def refresh_baseline(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Recompute this user's baseline for every metric with at least one
    non-null reading, from scratch, across their full check-in history.
    Metrics with zero non-null readings are left untouched (no row written).
    """
    for metric in METRICS:
        column = getattr(Checkin, metric)
        mean_value, sd_value, sample_n, min_value, max_value = (
            await session.execute(
                select(
                    func.avg(column),
                    func.stddev_samp(column),
                    func.count(column),
                    func.min(column),
                    func.max(column),
                ).where(Checkin.user_id == user_id, column.is_not(None))
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
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[UserBaseline.user_id, UserBaseline.metric],
            set_={
                "mean_value": stmt.excluded.mean_value,
                "sd_value": stmt.excluded.sd_value,
                "sample_n": stmt.excluded.sample_n,
                "min_value": stmt.excluded.min_value,
                "max_value": stmt.excluded.max_value,
                "computed_at": func.now(),
            },
        )
        await session.execute(stmt)

    await session.commit()
