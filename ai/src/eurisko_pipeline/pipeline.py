"""Application-facing orchestration for the three prediction stages.

The backend calls this module instead of knowing how the individual model
packages are wired together. Detailed check-ins run the CASE arousal model;
manual check-ins provide ``arousal_z`` directly and deliberately bypass it.
"""

from __future__ import annotations

from math import isfinite
from typing import Any, Mapping

from eurisko_arousal.trained_model import model as arousal_model
from eurisko_impulse.trained_model import model as impulse_model
from eurisko_overspending.trained_model import model as overspending_model

BASE_AROUSAL_FEATURE_NAMES = (
    "mean_hr_z",
    "hrv_sdnn_z",
    "mean_scr_z",
    "mean_resp_rate_z",
    "skin_temp_sd_z",
)

# Reference distribution from the 2,970 emotional CASE training windows.
CASE_AROUSAL_MEAN = 5.299964131313131
CASE_AROUSAL_STD = 1.4570462148483003


def _finite_number(name: str, value: object) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    try:
        numeric = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def _validated_arousal_values(inputs: Mapping[str, float]) -> dict[str, float]:
    expected = set(BASE_AROUSAL_FEATURE_NAMES)
    supplied = set(inputs)
    if supplied != expected:
        missing = sorted(expected - supplied)
        extra = sorted(supplied - expected)
        raise ValueError(f"Invalid arousal inputs: missing={missing}, extra={extra}")

    validated: dict[str, float] = {}
    for name in BASE_AROUSAL_FEATURE_NAMES:
        numeric = _finite_number(name, inputs[name])
        if not -3.0 <= numeric <= 3.0:
            raise ValueError(f"{name} must be between -3 and 3")
        validated[name] = numeric
    return validated


def complete_arousal_inputs(
    current: Mapping[str, float],
    values_30_seconds_ago: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """Add temporal deltas, using zero while no earlier sample exists."""

    current_values = _validated_arousal_values(current)
    earlier_values = (
        None
        if values_30_seconds_ago is None
        else _validated_arousal_values(values_30_seconds_ago)
    )
    completed = dict(current_values)
    for name, current_value in current_values.items():
        previous_value = current_value if earlier_values is None else earlier_values[name]
        completed[f"{name}_delta"] = current_value - previous_value
    return completed


def normalize_case_arousal(case_score: float) -> float:
    """Convert the original CASE rating to the impulse model's z-score."""

    numeric = _finite_number("CASE arousal score", case_score)
    return (numeric - CASE_AROUSAL_MEAN) / CASE_AROUSAL_STD


def run_pipeline(
    *,
    impulse_inputs: Mapping[str, Any],
    impulse_normalization: Mapping[str, Mapping[str, float]],
    budget_inputs: Mapping[str, float],
    arousal_inputs: Mapping[str, float] | None = None,
    direct_arousal_z: float | None = None,
    arousal_inputs_30_seconds_ago: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Run one complete prediction with exactly one arousal input mode."""

    if (arousal_inputs is None) == (direct_arousal_z is None):
        raise ValueError("Provide exactly one of arousal_inputs or direct_arousal_z")
    if direct_arousal_z is not None and arousal_inputs_30_seconds_ago is not None:
        raise ValueError("Manual arousal cannot include detailed arousal history")

    case_score: float | None
    if direct_arousal_z is not None:
        arousal_mode = "manual"
        case_score = None
        arousal_z = _finite_number("direct_arousal_z", direct_arousal_z)
        history_available = False
    else:
        arousal_mode = "detailed"
        complete_features = complete_arousal_inputs(
            arousal_inputs or {}, arousal_inputs_30_seconds_ago
        )
        case_score = arousal_model.predict(complete_features)
        arousal_z = normalize_case_arousal(case_score)
        history_available = arousal_inputs_30_seconds_ago is not None

    impulse_prediction = impulse_model.predict(
        normalization=impulse_normalization,
        arousal_z=arousal_z,
        **dict(impulse_inputs),
    )
    overspending_prediction = overspending_model.predict(
        z_ib=impulse_prediction.z_ib,
        **dict(budget_inputs),
    )

    if overspending_prediction.z_ib != impulse_prediction.z_ib:
        raise RuntimeError("Z_IB changed between the two prediction stages")

    return {
        "arousal": {
            "mode": arousal_mode,
            "case_score": case_score,
            "arousal_z_passed": arousal_z,
            "history_available": history_available,
        },
        "z_ib_passed": impulse_prediction.z_ib,
        "impulse": impulse_prediction.as_dict(),
        "overspending": overspending_prediction.as_dict(),
    }
