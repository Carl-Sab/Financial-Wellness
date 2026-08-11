"""GET /api/v1/spending/summary — the bank page's daily/weekly/monthly
spend overview, all windows computed in the user's own timezone (from
users.timezone), not the server's.
"""

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

router = APIRouter(prefix="/spending", tags=["spending"])


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
    session: AsyncSession, user_id: object, window_start: datetime, window_end: datetime
) -> Decimal:
    query = select(sa_func.coalesce(sa_func.sum(Transaction.amount), 0)).where(
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
    # correspond to total spend. Never derived by dividing a monthly goal
    # into a daily/weekly figure — a derived budget that looks user-set is
    # misleading, so this returns None (not a computed value) whenever no
    # matching goal exists for that exact period.
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


async def _window_summary(
    session: AsyncSession,
    user_id: object,
    period: str,
    period_start: date,
    period_end: date,
    window_start: datetime,
    window_end: datetime,
) -> SpendingWindow:
    spent = await _spent(session, user_id, window_start, window_end)
    goal = await _active_period_goal(session, user_id, period)
    target = goal.target_amount if goal is not None else None
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
        session, current_user.id, "daily", today_local, today_local, daily_start, daily_end
    )
    weekly = await _window_summary(
        session, current_user.id, "weekly", week_start_local, today_local, weekly_start, weekly_end
    )
    monthly = await _window_summary(
        session,
        current_user.id,
        "monthly",
        month_start_local,
        today_local,
        monthly_start,
        monthly_end,
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
