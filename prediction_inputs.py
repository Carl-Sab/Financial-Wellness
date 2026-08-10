"""Edit the inputs below, then run this file to execute both models."""

from __future__ import annotations

import json
from typing import Any


# Already-derived, neutral-relative CASE features for the arousal model.
AROUSAL_INPUTS = {
    "mean_hr_z": -5,
    "hrv_sdnn_z": 5,
    "mean_scr_z": 1.1,
    "mean_resp_rate_z": -1,
    "skin_temp_sd_z": 0.2,


    "mean_hr_z_delta": 0.0,
    "hrv_sdnn_z_delta": 0.0,
    "mean_scr_z_delta": 0.0,
    "mean_resp_rate_z_delta": 0.0,
    "skin_temp_sd_z_delta": 0.0,
}


# Reference distribution from the 2,970 emotional CASE training windows.
CASE_AROUSAL_MEAN = 5.299964131313131
CASE_AROUSAL_STD = 1.4570462148483003


# Inputs for the impulse model. Arousal is intentionally absent because the
# pipeline predicts and standardizes it directly from AROUSAL_INPUTS.
IMPULSE_INPUTS = {
    #signup
    "buying_impulsiveness": 2,
    "hedonic_value": 4.8,
    "utilitarian_value": 4.1,
    "normative_evaluation": 3.0,
    "self_control": 2,


    #Questions
    "store_category": "Groceries",
    #slider -2->2 #

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


def run_pipeline() -> dict[str, Any]:
    """Run arousal, impulse, and overspending prediction in sequence."""

    from eurisko_arousal.trained_model import model as arousal_model
    from eurisko_impulse.trained_model import NORMALIZATION, model as impulse_model
    from eurisko_overspending.trained_model import model as overspending_model

    arousal_score = arousal_model.predict(AROUSAL_INPUTS)
    arousal_z = (arousal_score - CASE_AROUSAL_MEAN) / CASE_AROUSAL_STD
    impulse_prediction = impulse_model.predict(
        normalization=NORMALIZATION,
        arousal_z=arousal_z,
        **IMPULSE_INPUTS,
    )
    overspending_prediction = overspending_model.predict(
        z_ib=impulse_prediction.z_ib,
        **BUDGET_INPUTS,
    )

    if overspending_prediction.z_ib != impulse_prediction.z_ib:
        raise RuntimeError("Z_IB changed between the two prediction stages")

    return {
        "arousal": {
            "case_score": arousal_score,
            "arousal_z_passed": arousal_z,
        },
        "z_ib_passed": impulse_prediction.z_ib,
        "impulse": impulse_prediction.as_dict(),
        "overspending": overspending_prediction.as_dict(),
    }


if __name__ == "__main__":
    print(json.dumps(run_pipeline(), indent=2))
