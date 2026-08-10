"""Arousal scoring: compares a check-in's readings to the user's own baseline.

Arousal-scoring domain. Nothing here may import from wellness.models.transactions,
wellness.models.financial, wellness.models.banking, or wellness.models.goals —
see the boundary comment at the top of wellness.models.transactions. Arousal is
computed from physiology alone; spending data plays no role.
"""

import math
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.models.arousal import ArousalState
from wellness.models.baseline import UserBaseline
from wellness.models.biometric_samples import BiometricSample
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

# Metrics biometric_samples can supply a window reading for. eda_microsiemens
# and skin_temp_c have no wearable equivalent and always come from the
# typed check-in value.
_SAMPLE_METRICS = ("heart_rate", "hrv_ms", "spo2_percent")

WINDOW_BEFORE_CHECKIN = timedelta(minutes=15)
MIN_WINDOW_SAMPLES = 3


class CheckinNotFoundError(LookupError):
    pass


async def _resolve_reading(
    session: AsyncSession, checkin: Checkin, metric: str
) -> tuple[float | None, str, int]:
    """The reading to score for `metric`: the average of biometric_samples in
    the 15 minutes before the check-in when at least MIN_WINDOW_SAMPLES exist
    there, otherwise the value typed into the check-in itself. Returns
    (reading, source, samples_in_window) where source is 'samples' or
    'checkins' and samples_in_window is only meaningful when source is
    'samples'.
    """
    typed_value: float | None = getattr(checkin, metric)
    if metric not in _SAMPLE_METRICS:
        return typed_value, "checkins", 0

    sample_column = getattr(BiometricSample, metric)
    avg_value, sample_count = (
        await session.execute(
            select(func.avg(sample_column), func.count(sample_column)).where(
                BiometricSample.user_id == checkin.user_id,
                sample_column.is_not(None),
                BiometricSample.ts.between(
                    checkin.entered_at - WINDOW_BEFORE_CHECKIN, checkin.entered_at
                ),
            )
        )
    ).one()

    if sample_count >= MIN_WINDOW_SAMPLES:
        return avg_value, "samples", sample_count
    return typed_value, "checkins", 0


def _baseline_factor(baseline: UserBaseline) -> float:
    """How reliable a baseline is, 0-1. Baselines built from wearable
    samples are trusted at lower n than checkin-built ones since a sample
    is passively collected rather than typed in.
    """
    if baseline.source == "samples":
        if baseline.sample_n >= 100:
            return 1.0
        if baseline.sample_n >= 30:
            return 0.75
        return 0.0
    if baseline.sample_n < 8:
        return 0.0
    if baseline.sample_n < 20:
        return 0.5
    return 1.0


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
    baseline_factors_used: list[float] = []
    window_sample_count = 0
    any_sample_sourced = False

    for metric, (z_field, sign) in _METRIC_SPEC.items():
        baseline = baselines.get(metric)
        if baseline is None:
            continue
        if baseline.sd_value is None or baseline.sd_value == 0:
            continue

        reading, metric_source, samples_in_window = await _resolve_reading(
            session, checkin, metric
        )
        if reading is None:
            continue

        z = (reading - baseline.mean_value) / baseline.sd_value
        z_scores[z_field] = z
        signed_terms.append(sign * z)
        baseline_factors_used.append(_baseline_factor(baseline))

        if metric_source == "samples":
            any_sample_sourced = True
            window_sample_count += samples_in_window

    metrics_used = len(signed_terms)
    score = 1 / (1 + math.exp(-(sum(signed_terms) / metrics_used))) if metrics_used else None

    baseline_factor = min(baseline_factors_used) if baseline_factors_used else 0.0
    confidence = max(0.0, min(1.0, 0.2 * metrics_used * baseline_factor))
    reading_source = "samples" if any_sample_sourced else "checkins"

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
        "window_sample_count": window_sample_count,
        "reading_source": reading_source,
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
            "window_sample_count": stmt.excluded.window_sample_count,
            "reading_source": stmt.excluded.reading_source,
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
