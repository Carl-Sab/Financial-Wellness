"""Adapter from application records to the packaged prediction pipeline."""

from __future__ import annotations

from typing import Literal

from eurisko_pipeline.pipeline import run_pipeline
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.models import (
    Category,
    Checkin,
    QuestionnaireResponse,
    User,
    UserNormalizationSnapshot,
)
from wellness.models.enums import ValenceLevel
from wellness.schemas.predictions import CheckinPredictionRead
from wellness.schemas.spending import SpendingSummary

_VALENCE_VALUES = {
    ValenceLevel.VERY_UNPLEASANT: -2,
    ValenceLevel.UNPLEASANT: -1,
    ValenceLevel.NEUTRAL: 0,
    ValenceLevel.PLEASANT: 1,
    ValenceLevel.VERY_PLEASANT: 2,
}

_RISK_MESSAGES = {
    "low": "Your current spending pattern is in the low-risk range.",
    "medium": "Your current spending pattern shows a moderate overspending risk.",
    "high": "Your current spending pattern shows a high overspending risk.",
}


def overspending_risk_level(probability: float) -> Literal["low", "medium", "high"]:
    """Apply the product's hard-coded 33% and 66% display bands."""

    if probability < 0.33:
        return "low"
    if probability <= 0.66:
        return "medium"
    return "high"


def _require_persona(response: QuestionnaireResponse | None) -> QuestionnaireResponse:
    if response is None:
        raise HTTPException(status_code=409, detail="Complete the questionnaire first")

    required = (
        response.impulse_tendency_score,
        response.self_control_score,
        response.hedonic_score,
        response.utilitarian_score,
        response.normative_eval_score,
    )
    if any(value is None for value in required):
        raise HTTPException(status_code=409, detail="Questionnaire scores are incomplete")
    return response


def _normalization(snapshot: UserNormalizationSnapshot) -> dict[str, dict[str, float]]:
    return {
        "T": {"mu": snapshot.impulse_tendency_mean, "std": snapshot.impulse_tendency_std},
        "H": {"mu": snapshot.hedonic_mean, "std": snapshot.hedonic_std},
        "U": {"mu": snapshot.utilitarian_mean, "std": snapshot.utilitarian_std},
        "N": {
            "mu": snapshot.normative_evaluation_mean,
            "std": snapshot.normative_evaluation_std,
        },
        "SC": {"mu": snapshot.self_control_mean, "std": snapshot.self_control_std},
    }


def _detailed_arousal(checkin: Checkin) -> dict[str, float]:
    values = {
        "mean_hr_z": checkin.perceived_heart_rate,
        # A steadier heartbeat means less beat-to-beat variability (HRV),
        # so this subjective proxy has the opposite sign from HRV SDNN.
        "hrv_sdnn_z": (
            None
            if checkin.perceived_heartbeat_steadiness is None
            else -checkin.perceived_heartbeat_steadiness
        ),
        "mean_scr_z": checkin.perceived_sweating,
        "mean_resp_rate_z": checkin.perceived_respiration,
        "skin_temp_sd_z": checkin.perceived_temperature_difference,
    }
    if any(value is None for value in values.values()):
        raise HTTPException(status_code=409, detail="Detailed arousal inputs are incomplete")
    return {name: float(value) for name, value in values.items() if value is not None}


async def predict_checkin(
    session: AsyncSession,
    user: User,
    checkin: Checkin,
    spending: SpendingSummary,
) -> CheckinPredictionRead:
    questionnaire = _require_persona(
        (
            await session.execute(
                select(QuestionnaireResponse).where(
                    QuestionnaireResponse.user_id == user.id
                )
            )
        ).scalar_one_or_none()
    )
    snapshot = (
        await session.execute(
            select(UserNormalizationSnapshot)
            .where(UserNormalizationSnapshot.user_id == user.id)
            .order_by(
                UserNormalizationSnapshot.recorded_at.desc(),
                UserNormalizationSnapshot.id.desc(),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(status_code=409, detail="Normalization snapshot is missing")

    category = await session.get(Category, checkin.category_code)
    if category is None:
        raise HTTPException(status_code=409, detail="Check-in category is missing")

    windows = (spending.daily, spending.weekly, spending.monthly)
    if any(window.target is None for window in windows):
        raise HTTPException(status_code=409, detail="Set a monthly budget first")
    if any(window.target is not None and window.target <= 0 for window in windows):
        raise HTTPException(status_code=409, detail="Budget targets must be greater than zero")

    impulse_inputs = {
        "buying_impulsiveness": questionnaire.impulse_tendency_score,
        "hedonic_value": questionnaire.hedonic_score,
        "utilitarian_value": questionnaire.utilitarian_score,
        "normative_evaluation": questionnaire.normative_eval_score,
        "self_control": questionnaire.self_control_score,
        "marketing_score": category.marketing_score,
        "valence": _VALENCE_VALUES[checkin.valence],
    }
    budget_inputs = {
        "daily_budget": float(spending.daily.target),
        "daily_spent_before": float(spending.daily.spent),
        "weekly_budget": float(spending.weekly.target),
        "weekly_spent_before": float(spending.weekly.spent),
        "monthly_budget": float(spending.monthly.target),
        "monthly_spent_before": float(spending.monthly.spent),
    }

    try:
        if checkin.arousal_input_mode == "manual":
            if checkin.arousal_z is None:
                raise HTTPException(status_code=409, detail="Manual arousal input is missing")
            result = run_pipeline(
                direct_arousal_z=checkin.arousal_z,
                impulse_inputs=impulse_inputs,
                impulse_normalization=_normalization(snapshot),
                budget_inputs=budget_inputs,
            )
        elif checkin.arousal_input_mode == "detailed":
            result = run_pipeline(
                arousal_inputs=_detailed_arousal(checkin),
                impulse_inputs=impulse_inputs,
                impulse_normalization=_normalization(snapshot),
                budget_inputs=budget_inputs,
            )
        else:
            raise HTTPException(status_code=409, detail="Check-in arousal mode is missing")
    except ValueError as exc:
        raise HTTPException(
            status_code=409, detail=f"Prediction inputs are invalid: {exc}"
        ) from exc

    probability = float(result["overspending"]["probability"])
    risk_level = overspending_risk_level(probability)
    arousal = result["arousal"]
    return CheckinPredictionRead(
        checkin_id=checkin.id,
        arousal_input_mode=checkin.arousal_input_mode,
        arousal_z=float(arousal["arousal_z_passed"]),
        arousal_case_score=(
            None if arousal["case_score"] is None else float(arousal["case_score"])
        ),
        impulse_z=float(result["z_ib_passed"]),
        overspending_probability=probability,
        overspending_percentage=round(probability * 100),
        risk_level=risk_level,
        message=_RISK_MESSAGES[risk_level],
    )
