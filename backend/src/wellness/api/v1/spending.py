"""GET /api/v1/spending/summary — the bank page's daily/weekly/monthly
spend overview, all windows computed in the user's own timezone (from
users.timezone), not the server's.
"""

import calendar
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends
from sqlalchemy import case, select
from sqlalchemy import func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import get_current_user
from wellness.api.v1.goals import _daily_window
from wellness.db import get_session
from wellness.models import BankAccount, Transaction, User, UserGoal
from wellness.models.enums import TransactionDirection
from wellness.schemas.spending import SpendingSummary, SpendingWindow
from wellness.services.currency import convert, converted_amount_expr, quantize

router = APIRouter(prefix="/spending", tags=["spending"])

def _resolve_timezone(name: str) -> ZoneInfo:
    # Same fallback as goals.py's _daily_window: an invalid IANA name
    # degrades to UTC rather than 500ing.
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _current_month_bounds(user_timezone: str) -> tuple[date, date]:
    """Today's date and the last day of its calendar month, both in the
    user's own timezone. Used by monthly_goals.py to scope a new monthly
    goal to "the rest of this calendar month" regardless of which day it's
    created on.
    """
    tz = _resolve_timezone(user_timezone)
    today_local = datetime.now(tz).date()
    days_in_month = calendar.monthrange(today_local.year, today_local.month)[1]
    return today_local, today_local.replace(day=days_in_month)


def _weekly_window(user_timezone: str) -> tuple[date, datetime, datetime]:
    """Monday 00:00 through now, in the user's own timezone."""
    tz = _resolve_timezone(user_timezone)
    now_local = datetime.now(tz)
    monday_local = (now_local - timedelta(days=now_local.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return monday_local.date(), monday_local.astimezone(UTC), now_local.astimezone(UTC)


def _monthly_window(user_timezone: str) -> tuple[date, datetime, datetime]:
    """The 1st of the current month, 00:00, through now, in the user's own
    timezone."""
    tz = _resolve_timezone(user_timezone)
    now_local = datetime.now(tz)
    month_start_local = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return month_start_local.date(), month_start_local.astimezone(UTC), now_local.astimezone(UTC)


async def _spent(
    session: AsyncSession,
    user_id: object,
    window_start: datetime,
    window_end: datetime,
    display_currency: str,
) -> Decimal:
    amount_expr = converted_amount_expr(Transaction.amount, Transaction.currency, display_currency)
    query = select(sa_func.coalesce(sa_func.sum(amount_expr), 0)).where(
        Transaction.user_id == user_id,
        Transaction.direction == TransactionDirection.DEBIT,
        Transaction.occurred_at >= window_start,
        Transaction.occurred_at < window_end,
    )
    result: Decimal = (await session.execute(query)).scalar_one()
    return result


def _effective_monthly_end(starts_on: date, ends_on: date | None) -> date:
    """A monthly-period goal's real closing date.

    A goal created before monthly goals were scoped to a single calendar
    month (namely onboarding.py's first-ever budget) has ends_on=None,
    meaning "never ends" under the old single-open-ended-goal model. Under
    per-month scoping that would make it cover every future month forever
    and rollover would never trigger, so an unset ends_on on a monthly goal
    is treated as ending at the close of its own starting month — not as
    open-ended. An explicit ends_on earlier than that still wins.
    """
    days_in_month = calendar.monthrange(starts_on.year, starts_on.month)[1]
    month_end = starts_on.replace(day=days_in_month)
    return min(ends_on, month_end) if ends_on is not None else month_end


async def _active_period_goal(
    session: AsyncSession, user_id: object, period: str, today: date
) -> UserGoal | None:
    # category_code IS NULL: "spent" here is always all-categories, so the
    # only goal that can meaningfully supply a target/remaining for it is
    # one that's also all-categories — a category_cap goal wouldn't
    # correspond to total spend. This only ever returns a goal whose period
    # column matches exactly — weekly/daily derivation from a monthly goal
    # happens one level up, in _window_summary, so an explicit weekly/daily
    # goal (if one exists) always takes priority over a derived figure.
    #
    # Filtered and clamped in Python rather than SQL: the monthly-only
    # ends_on clamp above isn't expressible as a simple column comparison,
    # and the candidate set here is always tiny (a handful of goals per
    # user at most).
    result = await session.execute(
        select(UserGoal)
        .where(
            UserGoal.user_id == user_id,
            UserGoal.period == period,
            UserGoal.category_code.is_(None),
            UserGoal.is_active.is_(True),
        )
        .order_by(UserGoal.created_at.desc())
    )
    for goal in result.scalars().all():
        if goal.starts_on > today:
            continue
        effective_end = (
            _effective_monthly_end(goal.starts_on, goal.ends_on) if period == "monthly" else goal.ends_on
        )
        if effective_end is not None and effective_end < today:
            continue
        return goal
    return None


async def _provisional_monthly_goal(session: AsyncSession, user_id: object) -> UserGoal | None:
    """Last month's monthly_budget goal, carried forward for display only.

    Used when no monthly_budget goal covers today at all — the gap between a
    month rolling over and the user actually setting/accepting this month's
    goal via POST /api/v1/goals/monthly. Not a real target for the current
    period, just prevents Bank/Home from flashing "no budget set" during
    that gap; callers must mark the result is_provisional so the frontend
    can label it as such.
    """
    result = await session.execute(
        select(UserGoal)
        .where(UserGoal.user_id == user_id, UserGoal.goal_type == "monthly_budget")
        .order_by(UserGoal.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _period_allocation_end(period: str, period_start: date) -> date:
    if period == "daily":
        return period_start
    if period == "weekly":
        return period_start + timedelta(days=6)
    days_in_month = calendar.monthrange(period_start.year, period_start.month)[1]
    return period_start.replace(day=days_in_month)


def _derived_target(
    monthly_target: Decimal,
    period: str,
    period_start: date,
    goal_starts_on: date,
    goal_ends_on: date | None,
) -> Decimal:
    """Sum the monthly budget's calendar-day allocations for a period.

    Each day is worth ``monthly_target / number of days in that day's
    month``. Consequently, a week crossing a month boundary contains a
    weighted share of both months instead of the inaccurate monthly/4
    approximation. The first month is prorated inclusively from the day the
    budget becomes active.

    ``monthly_target`` must already be in the display currency. We quantize
    only the final sum so currency conversion and per-day rounding errors do
    not compound.
    """
    allocation_start = max(period_start, goal_starts_on)
    allocation_end = _period_allocation_end(period, period_start)
    if goal_ends_on is not None:
        allocation_end = min(allocation_end, goal_ends_on)
    if allocation_start > allocation_end:
        return Decimal("0.00")

    target = Decimal("0")
    allocation_day = allocation_start
    while allocation_day <= allocation_end:
        days_in_month = calendar.monthrange(
            allocation_day.year, allocation_day.month
        )[1]
        target += monthly_target / Decimal(days_in_month)
        allocation_day += timedelta(days=1)
    return quantize(target)


async def _window_summary(
    session: AsyncSession,
    user_id: object,
    period: str,
    period_start: date,
    period_end: date,
    window_start: datetime,
    window_end: datetime,
    display_currency: str,
    today: date,
) -> SpendingWindow:
    spent = await _spent(session, user_id, window_start, window_end, display_currency)

    goal = await _active_period_goal(session, user_id, period, today)
    target: Decimal | None = None
    is_provisional = False

    if goal is not None:
        converted_target = convert(goal.target_amount, goal.currency, display_currency)
        if period == "monthly":
            target = _derived_target(
                converted_target,
                period,
                period_start,
                goal.starts_on,
                goal.ends_on,
            )
        else:
            target = converted_target
    else:
        monthly_goal = (
            await _active_period_goal(session, user_id, "monthly", today)
            if period in ("weekly", "daily")
            else None
        )
        if monthly_goal is not None:
            monthly_target = convert(
                monthly_goal.target_amount,
                monthly_goal.currency,
                display_currency,
            )
            target = _derived_target(
                monthly_target,
                period,
                period_start,
                monthly_goal.starts_on,
                monthly_goal.ends_on,
            )
        else:
            provisional_goal = await _provisional_monthly_goal(session, user_id)
            if provisional_goal is not None:
                monthly_target = convert(
                    provisional_goal.target_amount,
                    provisional_goal.currency,
                    display_currency,
                )
                # The provisional goal's own starts_on/ends_on belong to a
                # past month and would clamp _derived_target to zero — treat
                # it as if it started fresh at the top of the current period
                # instead, so it allocates across this daily/weekly/monthly
                # window the same way a real goal would.
                target = _derived_target(monthly_target, period, period_start, period_start, None)
                is_provisional = True

    remaining = (target - spent) if target is not None else None
    return SpendingWindow(
        period_start=period_start,
        period_end=period_end,
        spent=spent,
        target=target,
        remaining=remaining,
        is_provisional=is_provisional,
    )


async def build_spending_summary(
    session: AsyncSession,
    current_user: User,
) -> SpendingSummary:
    today_local, daily_start, daily_end = _daily_window(current_user.timezone)
    week_start_local, weekly_start, weekly_end = _weekly_window(current_user.timezone)
    month_start_local, monthly_start, monthly_end = _monthly_window(current_user.timezone)

    daily = await _window_summary(
        session,
        current_user.id,
        "daily",
        today_local,
        today_local,
        daily_start,
        daily_end,
        current_user.currency,
        today_local,
    )
    weekly = await _window_summary(
        session,
        current_user.id,
        "weekly",
        week_start_local,
        today_local,
        weekly_start,
        weekly_end,
        current_user.currency,
        today_local,
    )
    monthly = await _window_summary(
        session,
        current_user.id,
        "monthly",
        month_start_local,
        today_local,
        monthly_start,
        monthly_end,
        current_user.currency,
        today_local,
    )

    opening_amount = converted_amount_expr(
        BankAccount.opening_balance,
        BankAccount.currency,
        current_user.currency,
    )
    opening_balance = (
        await session.execute(
            select(sa_func.coalesce(sa_func.sum(opening_amount), 0)).where(
                BankAccount.user_id == current_user.id
            )
        )
    ).scalar_one()

    movement_amount = converted_amount_expr(
        Transaction.amount,
        Transaction.currency,
        current_user.currency,
    )
    signed_amount = sa_func.sum(
        case(
            (Transaction.direction == TransactionDirection.CREDIT, movement_amount),
            else_=-movement_amount,
        )
    )
    movement_balance = (
        await session.execute(
            select(sa_func.coalesce(signed_amount, 0)).where(
                Transaction.user_id == current_user.id
            )
        )
    ).scalar_one()
    balance: Decimal = opening_balance + movement_balance

    return SpendingSummary(
        currency=current_user.currency,
        daily=daily,
        weekly=weekly,
        monthly=monthly,
        balance=balance,
    )


@router.get("/summary", response_model=SpendingSummary)
async def get_spending_summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SpendingSummary:
    return await build_spending_summary(session, current_user)
