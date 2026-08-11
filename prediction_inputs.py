"""Edit the inputs below, then run this file to execute both models."""

from __future__ import annotations

import json
from math import isfinite
from typing import Any, Mapping


# User/demo inputs: five already-derived neutral-relative CASE features.
# Each value must be between -3 and 3. Temporal deltas are derived internally.
AROUSAL_INPUTS = {
    """I need hear normalized"""
    "mean_hr_z": -3,

    """sliders"""
    "hrv_sdnn_z": 3, # here no prob directly from slider -2-->2
    "mean_scr_z": 1.1,# here no prob
    "mean_resp_rate_z": -1,# here no prob
    "skin_temp_sd_z": 0.2,# here no prob
}

BASE_AROUSAL_FEATURE_NAMES = tuple(AROUSAL_INPUTS)


# Reference distribution from the 2,970 emotional CASE training windows.

""" normalize arousal score to z-score for the impulse model. """
CASE_AROUSAL_MEAN = 5.299964131313131
CASE_AROUSAL_STD = 1.4570462148483003


# Inputs for the impulse model. Arousal is intentionally absent because the
# pipeline predicts and standardizes it directly from AROUSAL_INPUTS.
IMPULSE_INPUTS = {
    # Signup values
    "buying_impulsiveness": 2, # T from table
    "hedonic_value": 4.8,#H from table , generated mu/std
    "utilitarian_value": 4.1,#U from table , generated mu/std
    "normative_evaluation": 3.0,
    "self_control": 2,
    # Situation questions
    "store_category": "Groceries",
    # Slider: -2, -1, 0, 1, or 2
    "valence": 2,
}


# Inputs for the overspending model. Z_IB is intentionally absent because the
# pipeline receives it directly from the impulse model.
BUDGET_INPUTS = {
    "daily_budget": 50.0,
    "daily_spent_before": 30,
    "weekly_budget": 350.0,
    "weekly_spent_before": 240.0,
    "monthly_budget": 1500.0,
    "monthly_spent_before": 950.0,
}


def _validated_arousal_values(inputs: Mapping[str, float]) -> dict[str, float]:
    """Validate the five neutral-relative values exposed by the demo."""

    expected = set(BASE_AROUSAL_FEATURE_NAMES)
    supplied = set(inputs)
    if supplied != expected:
        missing = sorted(expected - supplied)
        extra = sorted(supplied - expected)
        raise ValueError(f"Invalid arousal inputs: missing={missing}, extra={extra}")

    validated: dict[str, float] = {}
    for name in BASE_AROUSAL_FEATURE_NAMES:
        value = inputs[name]
        if isinstance(value, bool):
            raise ValueError(f"{name} must be numeric")
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric") from exc
        if not isfinite(numeric) or not -3.0 <= numeric <= 3.0:
            raise ValueError(f"{name} must be finite and between -3 and 3")
        validated[name] = numeric
    return validated


def complete_arousal_inputs(
    current: Mapping[str, float],
    values_30_seconds_ago: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """Add model deltas, using zero during the demo's history warm-up."""

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
    """Convert the original CASE rating to the impulse model's z-score input."""

    numeric = float(case_score)
    if not isfinite(numeric):
        raise ValueError("CASE arousal score must be finite")
    return (numeric - CASE_AROUSAL_MEAN) / CASE_AROUSAL_STD


def run_pipeline(
    *,
    arousal_inputs: Mapping[str, float] | None = None,
    arousal_inputs_30_seconds_ago: Mapping[str, float] | None = None,
    impulse_inputs: Mapping[str, Any] | None = None,
    budget_inputs: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Run arousal, impulse, and overspending prediction in sequence."""

    from eurisko_arousal.trained_model import model as arousal_model
    from eurisko_impulse.trained_model import NORMALIZATION, model as impulse_model
    from eurisko_overspending.trained_model import model as overspending_model

    complete_features = complete_arousal_inputs(
        AROUSAL_INPUTS if arousal_inputs is None else arousal_inputs,
        arousal_inputs_30_seconds_ago,
    )
    selected_impulse_inputs = dict(
        IMPULSE_INPUTS if impulse_inputs is None else impulse_inputs
    )
    selected_budget_inputs = dict(BUDGET_INPUTS if budget_inputs is None else budget_inputs)

    arousal_score = arousal_model.predict(complete_features)
    arousal_z = normalize_case_arousal(arousal_score)
    impulse_prediction = impulse_model.predict(
        normalization=NORMALIZATION,
        arousal_z=arousal_z,
        **selected_impulse_inputs,
    )
    overspending_prediction = overspending_model.predict(
        z_ib=impulse_prediction.z_ib,
        **selected_budget_inputs,
    )

    if overspending_prediction.z_ib != impulse_prediction.z_ib:
        raise RuntimeError("Z_IB changed between the two prediction stages")

    return {
        "arousal": {
            "case_score": arousal_score,
            "arousal_z_passed": arousal_z,
            "history_available": arousal_inputs_30_seconds_ago is not None,
        },
        "z_ib_passed": impulse_prediction.z_ib,
        "impulse": impulse_prediction.as_dict(),
        "overspending": overspending_prediction.as_dict(),
    }


if __name__ == "__main__":
    print(json.dumps(run_pipeline(), indent=2))
