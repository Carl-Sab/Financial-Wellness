"""GET/POST /api/v1/goals/monthly — the current-month spending goal: status
(active vs. needs_setup-with-suggestion), and the endpoint that commits
either the suggested or a custom target for the new month.

Kept separate from onboarding.py (the very first budget, strictly one-shot)
and from goals.py (generic per-goal CRUD/progress, any goal_type/period).
This module owns the "there is exactly one active monthly_budget goal at a
time, and rolling into a new calendar month means the old one gets replaced"
lifecycle. Rollover is lazy: nothing runs on a schedule. GET /current simply
reports needs_setup with a suggestion when no monthly_budget goal covers
today; the new goal is only ever created by an explicit POST here — see
_provisional_monthly_goal in spending.py for how Bank/Home stay populated
during that gap without a real target existing yet.
"""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import get_current_user
from wellness.api.v1.onboarding import MONTHLY_BUDGET_GOAL_TYPE
from wellness.api.v1.spending import (
    _current_month_bounds,
    _effective_monthly_end,
    _resolve_timezone,
    _spent,
)
from wellness.db import get_session
from wellness.models import User, UserGoal
from wellness.schemas.goals import (
    MonthlyGoalProgress,
    MonthlyGoalStatus,
    MonthlyGoalSubmit,
    MonthlySuggestion,
    UserGoalRead,
)
from wellness.services.currency import convert, quantize

router = APIRouter(prefix="/goals/monthly", tags=["monthly_goals"])

# Last month's actual spend is at or above what was targeted: cut the new
# target to 80% of what was actually spent.
OVERSPEND_REDUCTION_FACTOR = Decimal("0.8")
# Last month's actual spend was under target: move only halfway from the old
# target toward actual spend, so a consistent underspender's target still
# trends down over successive months instead of freezing once they clear it.
UNDERSPEND_TIGHTEN_FACTOR = Decimal("0.5")
# Never suggest below half of the user's own original signup number — see
# _suggestion_floor for why this is a soft anchor, not a measured one.
SUGGESTION_FLOOR_FACTOR = Decimal("0.5")


async def _goal_covering(
    session: AsyncSession,
    user_id: object,
    range_start: date,
    range_end: date,
    *,
    active_only: bool,
) -> UserGoal | None:
    """Most recent monthly_budget goal overlapping [range_start, range_end].

    Filtered in Python (not SQL) using _effective_monthly_end, the same
    clamp spending.py's _active_period_goal applies — without it, an old
    open-ended goal (onboarding.py's first-ever budget has ends_on=None)
    would appear to cover every month forever and rollover would never
    trigger.
    """
    conditions = [UserGoal.user_id == user_id, UserGoal.goal_type == MONTHLY_BUDGET_GOAL_TYPE]
    if active_only:
        conditions.append(UserGoal.is_active.is_(True))
    result = await session.execute(
        select(UserGoal).where(*conditions).order_by(UserGoal.created_at.desc())
    )
    for goal in result.scalars().all():
        effective_end = _effective_monthly_end(goal.starts_on, goal.ends_on)
        if goal.starts_on <= range_end and effective_end >= range_start:
            return goal
    return None


def _previous_month_bounds(user_timezone: str) -> tuple[date, date, datetime, datetime]:
    tz = _resolve_timezone(user_timezone)
    this_month_start_local = datetime.now(tz).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    prev_month_end_date = this_month_start_local.date() - timedelta(days=1)
    prev_month_start_date = prev_month_end_date.replace(day=1)
    window_start = datetime.combine(prev_month_start_date, time.min, tz).astimezone(UTC)
    window_end = this_month_start_local.astimezone(UTC)
    return prev_month_start_date, prev_month_end_date, window_start, window_end


async def _suggestion_floor(session: AsyncSession, user_id: object, display_currency: str) -> Decimal:
    """Half of the user's own original signup budget.

    This is a *soft* anchor, not a measured one: the number it's based on is
    whatever the user self-reported at onboarding, not derived from actual
    spending history. Its only job is to stop the suggestion from spiraling
    toward zero across many accepted months — it is not a claim that half of
    that original figure is objectively affordable for this user.
    """
    result = await session.execute(
        select(UserGoal)
        .where(UserGoal.user_id == user_id, UserGoal.goal_type == MONTHLY_BUDGET_GOAL_TYPE)
        .order_by(UserGoal.created_at.asc())
        .limit(1)
    )
    first_goal = result.scalar_one_or_none()
    if first_goal is None:
        return Decimal("0.00")
    original = convert(first_goal.target_amount, first_goal.currency, display_currency)
    return quantize(original * SUGGESTION_FLOOR_FACTOR)


def _suggest_target(
    last_month_spent: Decimal, last_month_target: Decimal, floor_amount: Decimal
) -> Decimal:
    if last_month_spent >= last_month_target:
        suggested = last_month_spent * OVERSPEND_REDUCTION_FACTOR
    else:
        gap = last_month_target - last_month_spent
        suggested = last_month_target - gap * UNDERSPEND_TIGHTEN_FACTOR
    return max(quantize(suggested), quantize(floor_amount))


def _progress(goal: UserGoal, spent: Decimal) -> MonthlyGoalProgress:
    remaining = goal.target_amount - spent
    overage = max(Decimal("0.00"), -remaining)
    return MonthlyGoalProgress(
        target_amount=goal.target_amount,
        spent_amount=spent,
        remaining_amount=remaining,
        is_over=spent > goal.target_amount,
        overage_amount=overage,
    )


async def _suggestion_for(
    session: AsyncSession, current_user: User
) -> tuple[UserGoal, Decimal, MonthlySuggestion]:
    """Returns (last month's goal, last month's actual spend, the suggestion)
    or raises 404 if there's no prior monthly_budget goal to base one on."""
    prev_start, prev_end, prev_window_start, prev_window_end = _previous_month_bounds(
        current_user.timezone
    )
    prev_goal = await _goal_covering(session, current_user.id, prev_start, prev_end, active_only=False)
    if prev_goal is None:
        raise HTTPException(status_code=404, detail="No prior budget to base a suggestion on")

    last_month_spent = await _spent(
        session, current_user.id, prev_window_start, prev_window_end, prev_goal.currency
    )
    floor_amount = await _suggestion_floor(session, current_user.id, prev_goal.currency)
    amount = _suggest_target(last_month_spent, prev_goal.target_amount, floor_amount)
    basis = (
        "reduce_from_overspend"
        if last_month_spent >= prev_goal.target_amount
        else "tighten_from_underspend"
    )
    return prev_goal, last_month_spent, MonthlySuggestion(
        amount=amount, currency=prev_goal.currency, basis=basis
    )


@router.get("/current", response_model=MonthlyGoalStatus)
async def get_current_monthly_goal(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MonthlyGoalStatus:
    today_local, _month_end_local = _current_month_bounds(current_user.timezone)
    active_goal = await _goal_covering(
        session, current_user.id, today_local, today_local, active_only=True
    )

    if active_goal is not None:
        tz = _resolve_timezone(current_user.timezone)
        window_start = datetime.combine(active_goal.starts_on, time.min, tz).astimezone(UTC)
        window_end = datetime.now(UTC)
        spent = await _spent(session, current_user.id, window_start, window_end, active_goal.currency)
        return MonthlyGoalStatus(
            status="active",
            goal=UserGoalRead.model_validate(active_goal),
            progress=_progress(active_goal, spent),
        )

    _prev_goal, _spent_amount, suggestion = await _suggestion_for(session, current_user)
    return MonthlyGoalStatus(status="needs_setup", suggestion=suggestion)


@router.post("", response_model=UserGoalRead, status_code=201)
async def set_current_monthly_goal(
    payload: MonthlyGoalSubmit,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserGoal:
    today_local, month_end_local = _current_month_bounds(current_user.timezone)

    if (
        await _goal_covering(session, current_user.id, today_local, today_local, active_only=True)
        is not None
    ):
        raise HTTPException(status_code=409, detail="This month's budget is already set")

    if payload.accept_suggestion:
        _prev_goal, _spent_amount, suggestion = await _suggestion_for(session, current_user)
        target_amount = suggestion.amount
        currency = suggestion.currency
    else:
        if payload.target_amount is None:
            raise HTTPException(
                status_code=400,
                detail="target_amount is required unless accept_suggestion is true",
            )
        target_amount = payload.target_amount
        currency = payload.currency

    # Deactivate whatever monthly_budget goal was still flagged active
    # (normally last month's, past its own ends_on by now) so exactly one
    # stays active — the same invariant onboarding.py enforces for the very
    # first budget.
    stale_goals = await session.execute(
        select(UserGoal).where(
            UserGoal.user_id == current_user.id,
            UserGoal.goal_type == MONTHLY_BUDGET_GOAL_TYPE,
            UserGoal.is_active.is_(True),
        )
    )
    for stale_goal in stale_goals.scalars().all():
        stale_goal.is_active = False

    # starts_on is the day the goal is actually created, not the 1st of the
    # month: a goal set on the 10th only ever applied from the 10th onward,
    # so _derived_target's existing per-calendar-day proration already
    # handles a mid-month goal correctly, same as onboarding.py's first-ever
    # budget. ends_on is still the last day of *this* calendar month
    # regardless of when in the month starts_on falls.
    new_goal = UserGoal(
        user_id=current_user.id,
        goal_type=MONTHLY_BUDGET_GOAL_TYPE,
        category_code=None,
        target_amount=target_amount,
        currency=currency,
        period="monthly",
        starts_on=today_local,
        ends_on=month_end_local,
        is_active=True,
    )
    session.add(new_goal)
    await session.commit()
    await session.refresh(new_goal)
    return new_goal
