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
from wellness.models import BankAccount, BankLedger, Transaction, User, UserGoal
from wellness.models.enums import LedgerDirection
from wellness.schemas.spending import SpendingSummary, SpendingWindow
from wellness.services.currency import convert, converted_amount_expr, quantize

router = APIRouter(prefix="/spending", tags=["spending"])

# weekly = monthly / 4 flat; daily = monthly / days-in-that-calendar-month
# (28-31) — both fixed by product decision, not derived from anything else.
WEEKLY_DIVISOR = Decimal("4")


def _resolve_timezone(name: str) -> ZoneInfo:
    # Same fallback as goals.py's _daily_window: an invalid IANA name
    # degrades to UTC rather than 500ing.
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


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
        Transaction.occurred_at >= window_start,
        Transaction.occurred_at < window_end,
    )
    result: Decimal = (await session.execute(query)).scalar_one()
    return result


async def _active_period_goal(
    session: AsyncSession, user_id: object, period: str
) -> UserGoal | None:
    # category_code IS NULL: "spent" here is always all-categories, so the
    # only goal that can meaningfully supply a target/remaining for it is
    # one that's also all-categories — a category_cap goal wouldn't
    # correspond to total spend. This only ever returns a goal whose period
    # column matches exactly — weekly/daily derivation from a monthly goal
    # happens one level up, in _window_summary, so an explicit weekly/daily
    # goal (if one exists) always takes priority over a derived figure.
    result = await session.execute(
        select(UserGoal)
        .where(
            UserGoal.user_id == user_id,
            UserGoal.period == period,
            UserGoal.category_code.is_(None),
            UserGoal.is_active.is_(True),
        )
        .order_by(UserGoal.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _derived_target(monthly_target: Decimal, period: str, period_start: date) -> Decimal:
    """weekly -> monthly/4 flat; daily -> monthly/days-in-period_start's-month.
    monthly_target must already be converted into the display currency —
    converting first and dividing (quantizing once) after avoids compounding
    a 2dp rounding error at a 90,000:1 rate (e.g. rounding a USD/31 division
    to the cent before converting to LBP can be off by hundreds of LBP)."""
    if period == "weekly":
        return quantize(monthly_target / WEEKLY_DIVISOR)
    days_in_month = calendar.monthrange(period_start.year, period_start.month)[1]
    return quantize(monthly_target / Decimal(days_in_month))


async def _window_summary(
    session: AsyncSession,
    user_id: object,
    period: str,
    period_start: date,
    period_end: date,
    window_start: datetime,
    window_end: datetime,
    display_currency: str,
) -> SpendingWindow:
    spent = await _spent(session, user_id, window_start, window_end, display_currency)

    goal = await _active_period_goal(session, user_id, period)
    target: Decimal | None = None
    if goal is not None:
        target = convert(goal.target_amount, goal.currency, display_currency)
    elif period in ("weekly", "daily"):
        monthly_goal = await _active_period_goal(session, user_id, "monthly")
        if monthly_goal is not None:
            monthly_target = convert(monthly_goal.target_amount, monthly_goal.currency, display_currency)
            target = _derived_target(monthly_target, period, period_start)

    remaining = (target - spent) if target is not None else None
    return SpendingWindow(
        period_start=period_start,
        period_end=period_end,
        spent=spent,
        target=target,
        remaining=remaining,
    )


@router.get("/summary", response_model=SpendingSummary)
async def get_spending_summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
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
    )

    account_ids_query = select(BankAccount.id).where(BankAccount.user_id == current_user.id)
    signed_amount = sa_func.sum(
        case(
            (BankLedger.direction == LedgerDirection.CREDIT, BankLedger.amount),
            else_=-BankLedger.amount,
        )
    )
    balance_query = select(sa_func.coalesce(signed_amount, 0)).where(
        BankLedger.account_id.in_(account_ids_query)
    )
    balance: Decimal = (await session.execute(balance_query)).scalar_one()

    return SpendingSummary(
        currency=current_user.currency,
        daily=daily,
        weekly=weekly,
        monthly=monthly,
        balance=balance,
    )
