"""Mood-spending correlation analysis.

Spending-domain, read-only. This is the one place allowed to read across both
sides of the arousal/spending boundary: it imports wellness.models.checkins
and wellness.models.arousal (physiology) alongside wellness.models.transactions,
financial, and goals (spending), in order to compare mood against spending
behaviour — that comparison is the entire point of this module.

The boundary rule is one-directional, not mutual: the arousal-scoring domain
(wellness.models.checkins/baseline/arousal, wellness.services.baseline/arousal)
must never import spending. Nothing about that direction changes here — this
module is simply not part of either side. It is never imported BY anything in
the arousal domain, so wellness.services.baseline/arousal still cannot reach
spending data even transitively through this file. See
tests/test_domain_boundary.py, which this module is deliberately excluded
from (it isn't spending-domain code in the sense that test enforces; it's the
analysis layer sitting on top of both).
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.models.arousal import ArousalState
from wellness.models.checkins import Checkin
from wellness.models.enums import ArousalLabel, ValenceLevel
from wellness.models.financial import FinancialProfile
from wellness.models.goals import UserGoal
from wellness.models.transactions import Transaction
from wellness.schemas.analysis import (
    DailyBudget,
    MoodBucket,
    MoodSpendingPeriod,
    MoodSpendingResponse,
)
from wellness.services.currency import convert, converted_amount_expr

_MOOD_NAMES = ("stressed", "positive", "negative", "neutral", "unclassified")
_DAYS_PER_MONTH = Decimal("30")


async def _resolve_daily_budget(
    session: AsyncSession, user_id: uuid.UUID, display_currency: str
) -> tuple[Decimal | None, str]:
    """Priority order: active daily goal -> active monthly goal / 30 ->
    financial_profile.avg_monthly_spend / 30 -> none. Whatever source wins,
    its amount is converted into display_currency before being returned —
    a goal or profile can be denominated in a different currency than the
    transactions it's compared against.

    When more than one active goal matches a period, a whole-budget goal
    (category_code IS NULL) is preferred over a category-specific one, then
    the most recently created.
    """
    daily_goal = (
        await session.execute(
            select(UserGoal)
            .where(
                UserGoal.user_id == user_id,
                UserGoal.is_active.is_(True),
                UserGoal.period == "daily",
            )
            .order_by(UserGoal.category_code.is_not(None), UserGoal.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if daily_goal is not None:
        return convert(daily_goal.target_amount, daily_goal.currency, display_currency), "goal_daily"

    monthly_goal = (
        await session.execute(
            select(UserGoal)
            .where(
                UserGoal.user_id == user_id,
                UserGoal.is_active.is_(True),
                UserGoal.period == "monthly",
            )
            .order_by(UserGoal.category_code.is_not(None), UserGoal.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if monthly_goal is not None:
        monthly_target = convert(monthly_goal.target_amount, monthly_goal.currency, display_currency)
        return monthly_target / _DAYS_PER_MONTH, "goal_monthly"

    profile = (
        await session.execute(
            select(FinancialProfile).where(
                FinancialProfile.user_id == user_id, FinancialProfile.valid_to.is_(None)
            )
        )
    ).scalar_one_or_none()
    if profile is not None and profile.avg_monthly_spend is not None:
        monthly_spend = convert(profile.avg_monthly_spend, profile.currency, display_currency)
        return monthly_spend / _DAYS_PER_MONTH, "profile"

    return None, "none"


def _classify(
    label: ArousalLabel | None, valence: ValenceLevel | None, has_checkin: bool
) -> str | None:
    """Returns the mood bucket name, or None if the transaction is excluded
    from analysis entirely (unknown/missing arousal label). Order matters:
    stress is checked before valence.
    """
    if not has_checkin:
        return "unclassified"
    if label is None or label == ArousalLabel.UNKNOWN:
        return None
    if label == ArousalLabel.HIGH:
        return "stressed"
    if valence in (ValenceLevel.PLEASANT, ValenceLevel.VERY_PLEASANT):
        return "positive"
    if valence in (ValenceLevel.UNPLEASANT, ValenceLevel.VERY_UNPLEASANT):
        return "negative"
    return "neutral"


def _iter_periods(from_date: date, to_date: date, granularity: str) -> list[tuple[date, date]]:
    """Natural calendar weeks (Mon-Sun) or months, clipped to [from_date, to_date]."""
    periods: list[tuple[date, date]] = []
    cursor = from_date
    while cursor <= to_date:
        if granularity == "week":
            natural_start = cursor - timedelta(days=cursor.weekday())
            natural_end = natural_start + timedelta(days=6)
        else:
            natural_start = cursor.replace(day=1)
            next_month = (natural_start.replace(day=28) + timedelta(days=4)).replace(day=1)
            natural_end = next_month - timedelta(days=1)
        periods.append((max(natural_start, from_date), min(natural_end, to_date)))
        cursor = natural_end + timedelta(days=1)
    return periods


def _period_for_date(periods: list[tuple[date, date]], target: date) -> tuple[date, date] | None:
    for period in periods:
        if period[0] <= target <= period[1]:
            return period
    return None


async def get_mood_spending_analysis(
    session: AsyncSession,
    user_id: uuid.UUID,
    from_date: date,
    to_date: date,
    granularity: str,
    display_currency: str,
) -> MoodSpendingResponse:
    budget_amount, budget_source = await _resolve_daily_budget(session, user_id, display_currency)

    if budget_amount is None:
        return MoodSpendingResponse(
            daily_budget=DailyBudget(amount=None, source=budget_source),
            periods=[],
            currency=display_currency,
        )

    # Amounts convert to display_currency before summing/comparing, since a
    # user's transactions can be logged in a mix of LBP and USD.
    converted_amount = converted_amount_expr(Transaction.amount, Transaction.currency, display_currency)

    # Cumulative same-day spend, in transaction order — the window function
    # the task calls for, not a Python loop. ROWS (not the default RANGE)
    # frame + an `id` tiebreak keeps this well-defined even when two
    # transactions share an occurred_at timestamp.
    running_total = func.sum(converted_amount).over(
        partition_by=(Transaction.user_id, func.date_trunc("day", Transaction.occurred_at)),
        order_by=(Transaction.occurred_at, Transaction.id),
        rows=(None, 0),
    )

    stmt = (
        select(
            converted_amount,
            Transaction.occurred_at,
            Transaction.checkin_id,
            Checkin.valence,
            ArousalState.label,
            running_total,
        )
        .select_from(Transaction)
        .outerjoin(Checkin, Checkin.id == Transaction.checkin_id)
        .outerjoin(ArousalState, ArousalState.checkin_id == Transaction.checkin_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.occurred_at >= from_date,
            Transaction.occurred_at < to_date + timedelta(days=1),
        )
        .order_by(Transaction.occurred_at, Transaction.id)
    )
    rows = (await session.execute(stmt)).all()

    periods = _iter_periods(from_date, to_date, granularity)
    bucket_data: dict[tuple[date, date], dict[str, list[tuple[Decimal, bool]]]] = {
        period: {mood: [] for mood in _MOOD_NAMES} for period in periods
    }

    for amount, occurred_at, checkin_id, valence, label, running in rows:
        mood = _classify(label, valence, checkin_id is not None)
        if mood is None:
            continue  # excluded: unknown/missing arousal label
        period = _period_for_date(periods, occurred_at.date())
        if period is None:
            continue  # outside the requested range; shouldn't happen
        bucket_data[period][mood].append((amount, running > budget_amount))

    period_results = []
    for period in periods:
        buckets = []
        for mood in _MOOD_NAMES:
            entries = bucket_data[period][mood]
            count = len(entries)
            overspend_count = sum(1 for _, flagged in entries if flagged)
            total = sum((amt for amt, _ in entries), Decimal("0"))
            buckets.append(
                MoodBucket(
                    mood=mood,
                    transaction_count=count,
                    overspend_count=overspend_count,
                    overspend_rate=(overspend_count / count) if count else 0.0,
                    avg_amount=(total / count) if count else Decimal("0"),
                    total_amount=total,
                )
            )
        period_results.append(
            MoodSpendingPeriod(period_start=period[0], period_end=period[1], buckets=buckets)
        )

    return MoodSpendingResponse(
        daily_budget=DailyBudget(amount=budget_amount, source=budget_source),
        periods=period_results,
        currency=display_currency,
    )
