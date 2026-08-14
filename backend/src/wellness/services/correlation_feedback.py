"""Friendly, non-technical feedback for the three daily relationship charts."""

from __future__ import annotations

import asyncio
import json
import math
import uuid
import warnings
from datetime import date
from typing import cast

import structlog
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.gateway import gateway_provider
from scipy import stats  # type: ignore[import-untyped]
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.config import get_settings
from wellness.schemas.analysis import (
    CorrelationClassification,
    CorrelationMetric,
    CorrelationResult,
    CorrelationSummaryResponse,
    CorrelationSummaryText,
    DailyMoodPoint,
    StatisticsView,
)
from wellness.services.analysis import get_daily_mood_points

logger = structlog.get_logger(__name__)

_METRICS: tuple[CorrelationMetric, ...] = (
    "positive_mood",
    "negative_mood",
    "arousal",
)

_AI_SYSTEM_PROMPT = """
You write a short, warm pattern summary for a personal financial wellness app.
You receive three server-calculated spending-pattern results. Return exactly
the requested structured fields.

Rules:
- Use everyday language. Never use: correlation, coefficient, p-value,
  statistically, significant, regression, or causation.
- Describe only what the supplied classification supports. Never invent a
  pattern, amount, date, diagnosis, personality trait, or reason.
- Use cautious phrases such as "looks like", "may", and "in this period".
- Never say that mood or arousal caused spending. Never shame, congratulate,
  or tell the user whether to make a purchase.
- If a result is insufficient_data, clearly say that more days or more varied
  entries are needed.
- Keep each field to one sentence of at most 28 words.
- The overall field summarizes all three results. The three metric fields each
  discuss only their named metric. The data_note states the evidence limit.
""".strip()

_TECHNICAL_WORDS = (
    "correlation",
    "coefficient",
    "p-value",
    "statistically",
    "significant",
    "regression",
    "causation",
)


def _classification(
    coefficient: float | None, p_value: float | None, days: int
) -> CorrelationClassification:
    if days < 7 or coefficient is None or p_value is None:
        return "insufficient_data"
    magnitude = abs(coefficient)
    if magnitude < 0.2:
        return "no_clear_pattern"
    direction = "positive" if coefficient > 0 else "negative"
    if days < 14 or p_value >= 0.05 or magnitude < 0.5:
        return cast(
            CorrelationClassification,
            f"possible_{direction}_pattern",
        )
    return cast(CorrelationClassification, f"clear_{direction}_pattern")


def _calculate_metric(
    points: list[DailyMoodPoint], metric: CorrelationMetric
) -> CorrelationResult:
    pairs = [
        (getattr(point, metric), point.normalized_spending)
        for point in points
        if getattr(point, metric) is not None
    ]
    coefficient: float | None = None
    p_value: float | None = None
    if len(pairs) >= 2:
        xs = [float(pair[0]) for pair in pairs]
        ys = [float(pair[1]) for pair in pairs]
        if len(set(xs)) > 1 and len(set(ys)) > 1:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", stats.ConstantInputWarning)
                result = stats.spearmanr(xs, ys)
            raw_coefficient = float(result.statistic)
            raw_p_value = float(result.pvalue)
            if math.isfinite(raw_coefficient) and math.isfinite(raw_p_value):
                coefficient = round(raw_coefficient, 4)
                p_value = round(raw_p_value, 4)

    return CorrelationResult(
        metric=metric,
        coefficient=coefficient,
        p_value=p_value,
        days_analyzed=len(pairs),
        classification=_classification(coefficient, p_value, len(pairs)),
    )


def calculate_correlations(points: list[DailyMoodPoint]) -> list[CorrelationResult]:
    return [_calculate_metric(points, metric) for metric in _METRICS]


def _metric_label(metric: CorrelationMetric) -> str:
    return {
        "positive_mood": "positive mood",
        "negative_mood": "more negative mood",
        "arousal": "arousal",
    }[metric]


def _template_metric(result: CorrelationResult) -> str:
    label = _metric_label(result.metric)
    classification = result.classification
    if classification == "insufficient_data":
        return (
            f"There are not enough varied days to compare your {label} and spending "
            "reliably yet."
        )
    if classification == "no_clear_pattern":
        return f"Your spending did not consistently rise or fall as your {label} changed."

    higher_spending = classification.endswith("positive_pattern")
    spending_direction = "higher" if higher_spending else "lower"
    if classification.startswith("possible"):
        return (
            f"Changes in your {label} sometimes appeared alongside {spending_direction} "
            "spending, but this early pattern may change."
        )
    return (
        f"Changes in your {label} often appeared alongside {spending_direction} spending "
        "in this period, though one does not prove the other."
    )


def build_template_summary(results: list[CorrelationResult]) -> CorrelationSummaryText:
    classifications = [result.classification for result in results]
    usable = [value for value in classifications if value != "insufficient_data"]
    if not usable:
        overall = (
            "There is not enough varied history in this period to describe a reliable "
            "pattern yet."
        )
    elif any(value.startswith("clear") for value in usable):
        overall = (
            "Your history shows at least one noticeable spending pattern in this period, "
            "while the other signals may be less consistent."
        )
    elif any(value.startswith("possible") for value in usable):
        overall = (
            "A few early spending patterns may be forming, but more history will show "
            "whether they continue."
        )
    else:
        overall = (
            "Your spending did not consistently move with the mood and arousal changes "
            "recorded in this period."
        )

    by_metric = {result.metric: result for result in results}
    maximum_days = max((result.days_analyzed for result in results), default=0)
    arousal_days = by_metric["arousal"].days_analyzed
    data_note = (
        f"This summary uses {maximum_days} recorded day{'s' if maximum_days != 1 else ''}; "
        f"arousal was available on {arousal_days}, and patterns may change as more entries "
        "are added."
    )
    return CorrelationSummaryText(
        overall=overall,
        positive_mood=_template_metric(by_metric["positive_mood"]),
        negative_mood=_template_metric(by_metric["negative_mood"]),
        arousal=_template_metric(by_metric["arousal"]),
        data_note=data_note,
    )


def _acceptable_ai_summary(summary: CorrelationSummaryText) -> bool:
    fields = (
        summary.overall,
        summary.positive_mood,
        summary.negative_mood,
        summary.arousal,
        summary.data_note,
    )
    return all(
        field.strip()
        and len(field.split()) <= 32
        and not any(word in field.lower() for word in _TECHNICAL_WORDS)
        for field in fields
    )


async def _generate_ai_summary(
    results: list[CorrelationResult], range_start: date, range_end: date
) -> CorrelationSummaryText | None:
    settings = get_settings()
    if not settings.gateway_api_key:
        return None

    provider = gateway_provider("anthropic", api_key=settings.gateway_api_key)
    model = AnthropicModel(settings.report_model, provider=provider)
    agent = Agent(
        model,
        output_type=CorrelationSummaryText,
        system_prompt=_AI_SYSTEM_PROMPT,
        retries={"output": 1},
    )
    prompt = json.dumps(
        {
            "range_start": range_start.isoformat(),
            "range_end": range_end.isoformat(),
            "results": [result.model_dump() for result in results],
        },
        default=str,
    )
    try:
        run_result = await asyncio.wait_for(agent.run(prompt), timeout=12)
    except Exception as exc:
        logger.warning("correlation_summary_ai_failed", error=str(exc))
        return None
    return run_result.output if _acceptable_ai_summary(run_result.output) else None


async def get_correlation_summary(
    session: AsyncSession,
    user_id: uuid.UUID,
    display_currency: str,
    user_timezone: str,
    view: StatisticsView,
    anchor: date,
) -> CorrelationSummaryResponse:
    range_start, range_end, points = await get_daily_mood_points(
        session=session,
        user_id=user_id,
        display_currency=display_currency,
        user_timezone=user_timezone,
        view=view,
        anchor=anchor,
    )
    results = calculate_correlations(points)
    fallback = build_template_summary(results)
    generated = await _generate_ai_summary(results, range_start, range_end)
    return CorrelationSummaryResponse(
        range_start=range_start,
        range_end=range_end,
        correlations=results,
        summary=generated or fallback,
        source="ai" if generated is not None else "template",
    )
