"""Arousal scoring: compares a check-in's readings to the user's own baseline.

Arousal-scoring domain. Nothing here may import from wellness.models.transactions,
wellness.models.financial, wellness.models.banking, or wellness.models.goals —
see the boundary comment at the top of wellness.models.transactions. Arousal is
computed from physiology alone; spending data plays no role.
"""

import math

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.models.arousal import ArousalState
from wellness.models.baseline import UserBaseline
from wellness.models.checkins import Checkin
from wellness.models.enums import ArousalLabel

MODEL_VERSION = "zscore-v1"

# metric name -> (ArousalState z-score field, sign of its contribution to arousal)
# HR, EDA and skin temp rise with arousal (+1); HRV and SpO2 fall with arousal (-1).
_METRIC_SPEC: dict[str, tuple[str, int]] = {
    "heart_rate": ("z_heart_rate", 1),
    "eda_microsiemens": ("z_eda", 1),
    "skin_temp_c": ("z_skin_temp", 1),
    "hrv_ms": ("z_hrv", -1),
    "spo2_percent": ("z_spo2", -1),
}


class CheckinNotFoundError(LookupError):
    pass


async def score_checkin(session: AsyncSession, checkin_id: int) -> ArousalState:
    checkin = await session.get(Checkin, checkin_id)
    if checkin is None:
        raise CheckinNotFoundError(f"checkin {checkin_id} not found")

    baselines_result = await session.execute(
        select(UserBaseline).where(UserBaseline.user_id == checkin.user_id)
    )
    baselines = {b.metric: b for b in baselines_result.scalars().all()}

    z_scores: dict[str, float] = {}
    signed_terms: list[float] = []
    sample_ns_used: list[int] = []

    for metric, (z_field, sign) in _METRIC_SPEC.items():
        reading = getattr(checkin, metric)
        baseline = baselines.get(metric)
        if reading is None or baseline is None:
            continue
        if baseline.sd_value is None or baseline.sd_value == 0:
            continue

        z = (reading - baseline.mean_value) / baseline.sd_value
        z_scores[z_field] = z
        signed_terms.append(sign * z)
        sample_ns_used.append(baseline.sample_n)

    metrics_used = len(signed_terms)
    score = 1 / (1 + math.exp(-(sum(signed_terms) / metrics_used))) if metrics_used else None

    if sample_ns_used:
        min_sample_n = min(sample_ns_used)
        if min_sample_n < 8:
            baseline_factor = 0.0
        elif min_sample_n < 20:
            baseline_factor = 0.5
        else:
            baseline_factor = 1.0
    else:
        baseline_factor = 0.0

    confidence = max(0.0, min(1.0, 0.2 * metrics_used * baseline_factor))

    if baseline_factor == 0.0 or metrics_used == 0:
        label = ArousalLabel.UNKNOWN
    elif score is not None and score < 0.4:
        label = ArousalLabel.CALM
    elif score is not None and score <= 0.7:
        label = ArousalLabel.ELEVATED
    else:
        label = ArousalLabel.HIGH

    values = {
        "checkin_id": checkin_id,
        "user_id": checkin.user_id,
        "z_heart_rate": z_scores.get("z_heart_rate"),
        "z_hrv": z_scores.get("z_hrv"),
        "z_eda": z_scores.get("z_eda"),
        "z_spo2": z_scores.get("z_spo2"),
        "z_skin_temp": z_scores.get("z_skin_temp"),
        "score": score,
        "label": label,
        "confidence": confidence,
        "metrics_used": metrics_used,
        "model_version": MODEL_VERSION,
    }

    stmt = insert(ArousalState).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[ArousalState.checkin_id],
        set_={
            "z_heart_rate": stmt.excluded.z_heart_rate,
            "z_hrv": stmt.excluded.z_hrv,
            "z_eda": stmt.excluded.z_eda,
            "z_spo2": stmt.excluded.z_spo2,
            "z_skin_temp": stmt.excluded.z_skin_temp,
            "score": stmt.excluded.score,
            "label": stmt.excluded.label,
            "confidence": stmt.excluded.confidence,
            "metrics_used": stmt.excluded.metrics_used,
            "model_version": stmt.excluded.model_version,
            "computed_at": func.now(),
        },
    )
    await session.execute(stmt)
    await session.commit()

    result = await session.execute(
        select(ArousalState).where(ArousalState.checkin_id == checkin_id)
    )
    return result.scalar_one()
