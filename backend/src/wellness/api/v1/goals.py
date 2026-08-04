# Smoke-test endpoints only — no auth. TODO: add real authentication before
# this is exposed beyond local smoke testing.
#
# No progress/current_spent is ever stored on user_goals — /progress below
# always recomputes it by summing transactions for the goal's period. See
# the boundary comment in wellness.models.goals.

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import PageParams, page_params
from wellness.api.errors import commit_or_409, not_found
from wellness.db import get_session
from wellness.models import Transaction, UserGoal
from wellness.schemas.goals import GoalProgress, UserGoalCreate, UserGoalRead, UserGoalUpdate

router = APIRouter(prefix="/goals", tags=["user_goals"])


@router.post("", response_model=UserGoalRead, status_code=201)
async def create_goal(
    payload: UserGoalCreate, session: AsyncSession = Depends(get_session)
) -> UserGoal:
    goal = UserGoal(**payload.model_dump())
    session.add(goal)
    await commit_or_409(session)
    await session.refresh(goal)
    return goal


@router.get("", response_model=list[UserGoalRead])
async def list_goals(
    pagination: PageParams = Depends(page_params),
    session: AsyncSession = Depends(get_session),
) -> list[UserGoal]:
    result = await session.execute(
        select(UserGoal)
        .order_by(UserGoal.created_at.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    return list(result.scalars().all())


@router.get("/{goal_id}", response_model=UserGoalRead)
async def get_goal(goal_id: int, session: AsyncSession = Depends(get_session)) -> UserGoal:
    goal = await session.get(UserGoal, goal_id)
    if goal is None:
        raise not_found("user_goal")
    return goal


@router.patch("/{goal_id}", response_model=UserGoalRead)
async def update_goal(
    goal_id: int, payload: UserGoalUpdate, session: AsyncSession = Depends(get_session)
) -> UserGoal:
    goal = await session.get(UserGoal, goal_id)
    if goal is None:
        raise not_found("user_goal")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, key, value)
    await commit_or_409(session)
    await session.refresh(goal)
    return goal


@router.delete("/{goal_id}", status_code=204)
async def delete_goal(goal_id: int, session: AsyncSession = Depends(get_session)) -> None:
    goal = await session.get(UserGoal, goal_id)
    if goal is None:
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


@router.get("/{goal_id}/progress", response_model=GoalProgress)
async def get_goal_progress(
    goal_id: int, session: AsyncSession = Depends(get_session)
) -> GoalProgress:
    goal = await session.get(UserGoal, goal_id)
    if goal is None:
        raise not_found("user_goal")

    period_start, period_end = _current_period(goal, date.today())

    query = select(sa_func.coalesce(sa_func.sum(Transaction.amount), 0)).where(
        Transaction.user_id == goal.user_id,
        Transaction.occurred_at >= period_start,
        Transaction.occurred_at < period_end + timedelta(days=1),
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
