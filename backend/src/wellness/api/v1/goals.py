# No progress/current_spent is ever stored on user_goals — /progress below
# always recomputes it by summing transactions for the goal's period. See
# the boundary comment in wellness.models.goals.

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import PageParams, get_current_user, page_params
from wellness.api.errors import commit_or_409, not_found
from wellness.db import get_session
from wellness.models import Transaction, User, UserGoal
from wellness.models.enums import TransactionDirection
from wellness.schemas.goals import GoalProgress, UserGoalCreate, UserGoalRead, UserGoalUpdate

router = APIRouter(prefix="/goals", tags=["user_goals"])


@router.post("", response_model=UserGoalRead, status_code=201)
async def create_goal(
    payload: UserGoalCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserGoal:
    goal = UserGoal(**payload.model_dump(), user_id=current_user.id)
    session.add(goal)
    await commit_or_409(session)
    await session.refresh(goal)
    return goal


@router.get("", response_model=list[UserGoalRead])
async def list_goals(
    pagination: PageParams = Depends(page_params),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[UserGoal]:
    result = await session.execute(
        select(UserGoal)
        .where(UserGoal.user_id == current_user.id)
        .order_by(UserGoal.created_at.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    return list(result.scalars().all())


@router.get("/{goal_id}", response_model=UserGoalRead)
async def get_goal(
    goal_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserGoal:
    goal = await session.get(UserGoal, goal_id)
    if goal is None or goal.user_id != current_user.id:
        raise not_found("user_goal")
    return goal


@router.patch("/{goal_id}", response_model=UserGoalRead)
async def update_goal(
    goal_id: int,
    payload: UserGoalUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserGoal:
    goal = await session.get(UserGoal, goal_id)
    if goal is None or goal.user_id != current_user.id:
        raise not_found("user_goal")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, key, value)
    await commit_or_409(session)
    await session.refresh(goal)
    return goal


@router.delete("/{goal_id}", status_code=204)
async def delete_goal(
    goal_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    goal = await session.get(UserGoal, goal_id)
    if goal is None or goal.user_id != current_user.id:
        raise not_found("user_goal")
    await session.delete(goal)
    await commit_or_409(session)


def _current_period(goal: UserGoal, today: date) -> tuple[date, date]:
    if goal.period == "weekly":
        period_start = today - timedelta(days=today.weekday())
        period_end = period_start + timedelta(days=6)
    else:
        period_start = today.replace(day=1)
        next_month = (period_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        period_end = next_month - timedelta(days=1)

    if goal.starts_on > period_start:
        period_start = goal.starts_on
    if goal.ends_on is not None and goal.ends_on < period_end:
        period_end = goal.ends_on
    return period_start, period_end


def _daily_window(user_timezone: str) -> tuple[date, datetime, datetime]:
    """Midnight through now, in the user's own timezone — not the whole
    calendar day, since 'now' partway through the day is the actual upper
    bound for a daily goal's progress. Falls back to UTC if the stored
    timezone name isn't a valid IANA zone.
    """
    try:
        tz = ZoneInfo(user_timezone)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")
    now_local = datetime.now(tz)
    midnight_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return now_local.date(), midnight_local.astimezone(UTC), now_local.astimezone(UTC)


@router.get("/{goal_id}/progress", response_model=GoalProgress)
async def get_goal_progress(
    goal_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GoalProgress:
    goal = await session.get(UserGoal, goal_id)
    if goal is None or goal.user_id != current_user.id:
        raise not_found("user_goal")

    window_start: date | datetime
    window_end: date | datetime

    if goal.period == "daily":
        period_start, window_start, window_end = _daily_window(current_user.timezone)
        period_end = period_start
    else:
        period_start, period_end = _current_period(goal, date.today())
        window_start = period_start
        window_end = period_end + timedelta(days=1)

    query = select(sa_func.coalesce(sa_func.sum(Transaction.amount), 0)).where(
        Transaction.user_id == goal.user_id,
        Transaction.direction == TransactionDirection.DEBIT,
        Transaction.occurred_at >= window_start,
        Transaction.occurred_at < window_end,
    )
    if goal.category_code is not None:
        query = query.where(Transaction.category_code == goal.category_code)

    spent_amount = (await session.execute(query)).scalar_one()
    return GoalProgress(
        goal_id=goal.id,
        period_start=period_start,
        period_end=period_end,
        target_amount=goal.target_amount,
        spent_amount=spent_amount,
        remaining_amount=goal.target_amount - spent_amount,
    )
