"""Edit the inputs below, then run this file to execute all three models."""

from __future__ import annotations

import json
from eurisko_impulse.trained_model import NORMALIZATION
from eurisko_pipeline.pipeline import run_pipeline


# User/demo inputs: five already-derived neutral-relative CASE features.
# Each value must be between -3 and 3. Temporal deltas are derived internally.
AROUSAL_INPUTS = {
    # Normalized heart rate.
    "mean_hr_z": -3,

    # Normalized user-entered stress parameters.
    "hrv_sdnn_z": 3,
    "mean_scr_z": 1.1,
    "mean_resp_rate_z": -1,
    "skin_temp_sd_z": 0.2,
}

# Inputs for the impulse model. Arousal is intentionally absent because the
# pipeline predicts and standardizes it directly from AROUSAL_INPUTS.
IMPULSE_INPUTS = {
    # Signup values
    "buying_impulsiveness": 2,  # T from the questionnaire
    "hedonic_value": 4.8,  # H from the questionnaire
    "utilitarian_value": 4.1,  # U from the questionnaire
    "normative_evaluation": 3.0,
    "self_control": 2,
    # Category value. The application loads this from
    # categories.marketing_score; 0.75 is the standalone Groceries example.
    "marketing_score": 0.75,
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


if __name__ == "__main__":
    print(
        json.dumps(
            run_pipeline(
                arousal_inputs=AROUSAL_INPUTS,
                impulse_inputs=IMPULSE_INPUTS,
                impulse_normalization=NORMALIZATION,
                budget_inputs=BUDGET_INPUTS,
            ),
            indent=2,
        )
    )
