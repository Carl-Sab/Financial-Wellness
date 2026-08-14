"""Read-only spending statistics assembled from canonical transaction data.

Nothing in this module is persisted: review totals, normalized spending, and
amount-weighted daily mood/arousal values are derived on request.
"""

from __future__ import annotations

import calendar
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from eurisko_arousal.trained_model import model as arousal_model  # type: ignore[import-untyped]
from eurisko_pipeline.pipeline import (  # type: ignore[import-untyped]
    complete_arousal_inputs,
    normalize_case_arousal,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.models.categories import Category
from wellness.models.checkins import Checkin
from wellness.models.enums import TransactionDirection, ValenceLevel
from wellness.models.goals import UserGoal
from wellness.models.transactions import Transaction
from wellness.schemas.analysis import (
    CategorySpendingItem,
    CategorySummary,
    CategoryView,
    DailyMoodPoint,
    SpendingReviewBucket,
    StatisticsBudget,
    StatisticsResponse,
    StatisticsView,
)
from wellness.services.currency import convert, quantize

_VALENCE_VALUES = {
    ValenceLevel.VERY_UNPLEASANT: -2.0,
    ValenceLevel.UNPLEASANT: -1.0,
    ValenceLevel.NEUTRAL: 0.0,
    ValenceLevel.PLEASANT: 1.0,
    ValenceLevel.VERY_PLEASANT: 2.0,
}


@dataclass(frozen=True)
class _TransactionRow:
    amount: Decimal
    day: date
    category_code: str | None
    category_label: str | None
    checkin: Checkin | None


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _month_end(value: date) -> date:
    return value.replace(day=calendar.monthrange(value.year, value.month)[1])


def _next_day(value: date) -> date:
    return value + timedelta(days=1)


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def _range_for_view(view: StatisticsView, anchor: date) -> tuple[date, date]:
    if view == "weekly":
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6)
    if view == "monthly":
        start = anchor.replace(day=1)
        return start, _month_end(start)
    return date(anchor.year, 1, 1), date(anchor.year, 12, 31)


def _range_for_category_view(view: CategoryView, anchor: date) -> tuple[date, date]:
    if view == "daily":
        return anchor, anchor
    if view == "weekly":
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6)
    if view == "monthly":
        start = anchor.replace(day=1)
        return start, _month_end(start)
    return date(anchor.year, 1, 1), date(anchor.year, 12, 31)


def _review_periods(
    view: StatisticsView, range_start: date, range_end: date
) -> list[tuple[str, date, date]]:
    if view == "weekly":
        return [(day.strftime("%a"), day, day) for day in _days(range_start, range_end)]
    if view == "yearly":
        return [
            (date(range_start.year, month, 1).strftime("%b"), date(range_start.year, month, 1),
             _month_end(date(range_start.year, month, 1)))
            for month in range(1, 13)
        ]

    periods: list[tuple[str, date, date]] = []
    cursor = range_start
    week_number = 1
    while cursor <= range_end:
        natural_end = cursor + timedelta(days=6 - cursor.weekday())
        end = min(natural_end, range_end)
        periods.append((f"Week {week_number}", cursor, end))
        cursor = end + timedelta(days=1)
        week_number += 1
    return periods


async def _monthly_budget(
    session: AsyncSession, user_id: uuid.UUID, display_currency: str
) -> tuple[Decimal | None, date | None, date | None]:
    goal = (
        await session.execute(
            select(UserGoal)
            .where(
                UserGoal.user_id == user_id,
                UserGoal.goal_type == "monthly_budget",
                UserGoal.category_code.is_(None),
                UserGoal.period == "monthly",
                UserGoal.is_active.is_(True),
            )
            .order_by(UserGoal.created_at.desc(), UserGoal.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if goal is None:
        return None, None, None
    return (
        convert(goal.target_amount, goal.currency, display_currency),
        goal.starts_on,
        goal.ends_on,
    )


def _daily_budget(
    monthly_amount: Decimal | None,
    starts_on: date | None,
    ends_on: date | None,
    day: date,
) -> Decimal:
    if monthly_amount is None or starts_on is None or day < starts_on:
        return Decimal("0")
    if ends_on is not None and day > ends_on:
        return Decimal("0")
    return monthly_amount / Decimal(calendar.monthrange(day.year, day.month)[1])


def _allocated_budget(
    monthly_amount: Decimal | None,
    starts_on: date | None,
    ends_on: date | None,
    period_start: date,
    period_end: date,
) -> Decimal:
    # Keep fractional cents while aggregating. Rounding every day or every
    # displayed week independently can make a month's buckets add up to a
    # different amount than the user's one monthly budget.
    return sum(
        (
            _daily_budget(monthly_amount, starts_on, ends_on, day)
            for day in _days(period_start, period_end)
        ),
        Decimal("0"),
    )


def _converted(amount: Decimal, currency: str, display_currency: str) -> Decimal:
    try:
        return convert(amount, currency, display_currency)
    except ValueError:
        # Transactions currently accept free-form currency codes. Preserve
        # the established display behavior for any historical unsupported row.
        return amount


def _detailed_arousal(checkin: Checkin) -> float | None:
    raw = {
        "mean_hr_z": checkin.perceived_heart_rate,
        "hrv_sdnn_z": (
            None
            if checkin.perceived_heartbeat_steadiness is None
            else -checkin.perceived_heartbeat_steadiness
        ),
        "mean_scr_z": checkin.perceived_sweating,
        "mean_resp_rate_z": checkin.perceived_respiration,
        "skin_temp_sd_z": checkin.perceived_temperature_difference,
    }
    if any(value is None for value in raw.values()):
        return None
    values = {name: float(value) for name, value in raw.items() if value is not None}
    score = arousal_model.predict(complete_arousal_inputs(values))
    return float(normalize_case_arousal(score))


def _arousal(checkin: Checkin) -> float | None:
    value: float | None
    if checkin.arousal_input_mode == "manual":
        value = None if checkin.arousal_z is None else float(checkin.arousal_z)
    elif checkin.arousal_input_mode == "detailed":
        value = _detailed_arousal(checkin)
    else:
        value = None
    if value is None:
        return None
    return max(-2.0, min(2.0, value))


async def _load_transactions(
    session: AsyncSession,
    user_id: uuid.UUID,
    display_currency: str,
    timezone: ZoneInfo,
    start: date,
    end: date,
) -> list[_TransactionRow]:
    start_utc = datetime.combine(start, time.min, tzinfo=timezone).astimezone(UTC)
    end_utc = datetime.combine(_next_day(end), time.min, tzinfo=timezone).astimezone(UTC)
    result = await session.execute(
        select(Transaction, Checkin, Category.label)
        .outerjoin(Checkin, Checkin.id == Transaction.checkin_id)
        .outerjoin(Category, Category.code == Transaction.category_code)
        .where(
            Transaction.user_id == user_id,
            Transaction.direction == TransactionDirection.DEBIT,
            Transaction.occurred_at >= start_utc,
            Transaction.occurred_at < end_utc,
        )
        .order_by(Transaction.occurred_at, Transaction.id)
    )
    return [
        _TransactionRow(
            amount=_converted(transaction.amount, transaction.currency, display_currency),
            day=transaction.occurred_at.astimezone(timezone).date(),
            category_code=transaction.category_code,
            category_label=category_label,
            checkin=checkin,
        )
        for transaction, checkin, category_label in result.all()
    ]


def _normalized_spending(spent: Decimal, budget: Decimal) -> float | None:
    if budget <= 0:
        return None
    return round(float(Decimal("2") * spent / budget), 4)


def _build_review(
    view: StatisticsView,
    range_start: date,
    range_end: date,
    rows: list[_TransactionRow],
    monthly_amount: Decimal | None,
    starts_on: date | None,
    ends_on: date | None,
) -> list[SpendingReviewBucket]:
    by_day: dict[date, list[_TransactionRow]] = defaultdict(list)
    for row in rows:
        if range_start <= row.day <= range_end:
            by_day[row.day].append(row)

    review: list[SpendingReviewBucket] = []
    for label, period_start, period_end in _review_periods(view, range_start, range_end):
        period_rows = [row for day in _days(period_start, period_end) for row in by_day[day]]
        spent = quantize(sum((row.amount for row in period_rows), Decimal("0")))
        budget = _allocated_budget(
            monthly_amount, starts_on, ends_on, period_start, period_end
        )
        normalized = _normalized_spending(spent, budget)
        review.append(
            SpendingReviewBucket(
                label=label,
                period_start=period_start,
                period_end=period_end,
                spent_amount=spent,
                budget_amount=budget,
                normalized_spending=normalized,
                overspent=None if normalized is None else normalized > 2,
                transaction_count=len(period_rows),
            )
        )
    return review


def _build_daily_mood(
    range_start: date,
    range_end: date,
    rows: list[_TransactionRow],
    monthly_amount: Decimal | None,
    starts_on: date | None,
    ends_on: date | None,
) -> list[DailyMoodPoint]:
    by_day: dict[date, list[_TransactionRow]] = defaultdict(list)
    for row in rows:
        if range_start <= row.day <= range_end:
            by_day[row.day].append(row)

    points: list[DailyMoodPoint] = []
    for day in sorted(by_day):
        day_rows = by_day[day]
        spent = quantize(sum((row.amount for row in day_rows), Decimal("0")))
        budget = _daily_budget(monthly_amount, starts_on, ends_on, day)
        normalized = _normalized_spending(spent, budget)
        if normalized is None:
            continue

        valence_rows = [row for row in day_rows if row.checkin is not None and row.amount > 0]
        valence_spend = sum((row.amount for row in valence_rows), Decimal("0"))
        if valence_spend <= 0:
            continue

        positive_total = Decimal("0")
        negative_total = Decimal("0")
        arousal_total = Decimal("0")
        arousal_spend = Decimal("0")
        for row in valence_rows:
            checkin = row.checkin
            if checkin is None:
                continue
            valence = Decimal(str(_VALENCE_VALUES[checkin.valence]))
            positive_total += row.amount * max(valence, Decimal("0"))
            negative_total += row.amount * max(-valence, Decimal("0"))
            arousal = _arousal(checkin)
            if arousal is not None:
                arousal_total += row.amount * Decimal(str(arousal))
                arousal_spend += row.amount

        points.append(
            DailyMoodPoint(
                day=day,
                positive_mood=round(float(positive_total / valence_spend), 4),
                negative_mood=round(float(negative_total / valence_spend), 4),
                arousal=(
                    None
                    if arousal_spend <= 0
                    else round(float(arousal_total / arousal_spend), 4)
                ),
                normalized_spending=normalized,
                spent_amount=spent,
                transaction_count=len(day_rows),
                checkin_transaction_count=len(valence_rows),
                checkin_spend_coverage=round(float(valence_spend / spent), 4) if spent > 0 else 0,
            )
        )
    return points


def _build_category_summary(
    view: CategoryView,
    range_start: date,
    range_end: date,
    rows: list[_TransactionRow],
    monthly_amount: Decimal | None,
    starts_on: date | None,
    ends_on: date | None,
) -> CategorySummary:
    category_totals: dict[tuple[str | None, str], Decimal] = defaultdict(Decimal)
    for row in rows:
        if range_start <= row.day <= range_end:
            key = (row.category_code, row.category_label or "Uncategorized")
            category_totals[key] += row.amount

    total_spent = quantize(sum(category_totals.values(), Decimal("0")))
    categories = [
        CategorySpendingItem(
            category_code=code,
            label=label,
            spent_amount=quantize(amount),
            share=round(float(amount / total_spent), 4) if total_spent > 0 else 0,
        )
        for (code, label), amount in sorted(
            category_totals.items(), key=lambda item: item[1], reverse=True
        )
    ]
    return CategorySummary(
        view=view,
        range_start=range_start,
        range_end=range_end,
        total_spent=total_spent,
        allocated_budget=_allocated_budget(
            monthly_amount, starts_on, ends_on, range_start, range_end
        ),
        categories=categories,
    )


async def get_daily_mood_points(
    session: AsyncSession,
    user_id: uuid.UUID,
    display_currency: str,
    user_timezone: str,
    view: StatisticsView,
    anchor: date,
) -> tuple[date, date, list[DailyMoodPoint]]:
    """Return the canonical points used by the three relationship charts.

    Correlation feedback intentionally reloads these server-side instead of
    accepting points from the browser, so the AI can only describe verified
    transaction and check-in data.
    """

    range_start, range_end = _range_for_view(view, anchor)
    monthly_amount, starts_on, ends_on = await _monthly_budget(
        session, user_id, display_currency
    )
    rows = await _load_transactions(
        session,
        user_id,
        display_currency,
        _timezone(user_timezone),
        range_start,
        range_end,
    )
    return (
        range_start,
        range_end,
        _build_daily_mood(
            range_start,
            range_end,
            rows,
            monthly_amount,
            starts_on,
            ends_on,
        ),
    )


async def get_statistics(
    session: AsyncSession,
    user_id: uuid.UUID,
    display_currency: str,
    user_timezone: str,
    view: StatisticsView,
    anchor: date,
    category_view: CategoryView,
    category_anchor: date,
) -> StatisticsResponse:
    range_start, range_end = _range_for_view(view, anchor)
    category_start, category_end = _range_for_category_view(category_view, category_anchor)
    query_start = min(range_start, category_start)
    query_end = max(range_end, category_end)

    monthly_amount, starts_on, ends_on = await _monthly_budget(
        session, user_id, display_currency
    )
    rows = await _load_transactions(
        session,
        user_id,
        display_currency,
        _timezone(user_timezone),
        query_start,
        query_end,
    )
    return StatisticsResponse(
        view=view,
        range_start=range_start,
        range_end=range_end,
        currency=display_currency,
        budget=StatisticsBudget(monthly_amount=monthly_amount, starts_on=starts_on),
        review=_build_review(
            view, range_start, range_end, rows, monthly_amount, starts_on, ends_on
        ),
        daily_mood=_build_daily_mood(
            range_start, range_end, rows, monthly_amount, starts_on, ends_on
        ),
        category_summary=_build_category_summary(
            category_view,
            category_start,
            category_end,
            rows,
            monthly_amount,
            starts_on,
            ends_on,
        ),
    )
