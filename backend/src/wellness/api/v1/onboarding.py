"""Post-questionnaire onboarding steps — currently just the monthly budget.

Distinct from POST /api/v1/goals (goals.py): that stays the unauthenticated,
unvalidated smoke-test CRUD endpoint it always was. This is the real flow —
authenticated, and enforced one-active-monthly-budget-per-user the same way
POST /api/v1/questionnaire enforces one questionnaire per user, though here
it's an application-level check rather than a DB constraint (a user_goal's
uniqueness isn't as clean to express at the schema level as
questionnaire_responses.user_id, since goal_type/is_active vary row to row).
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import get_current_user
from wellness.db import get_session
from wellness.models import User, UserGoal
from wellness.schemas.goals import UserGoalRead
from wellness.schemas.onboarding import BudgetSubmitRequest

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

MONTHLY_BUDGET_GOAL_TYPE = "monthly_budget"


async def _active_monthly_budget(session: AsyncSession, user_id: object) -> UserGoal | None:
    return (
        await session.execute(
            select(UserGoal).where(
                UserGoal.user_id == user_id,
                UserGoal.goal_type == MONTHLY_BUDGET_GOAL_TYPE,
                UserGoal.is_active.is_(True),
            )
        )
    ).scalars().first()


@router.post("/budget", response_model=UserGoalRead, status_code=201)
async def submit_budget(
    payload: BudgetSubmitRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserGoal:
    if await _active_monthly_budget(session, current_user.id) is not None:
        raise HTTPException(status_code=409, detail="Monthly budget already set")

    goal = UserGoal(
        user_id=current_user.id,
        goal_type=MONTHLY_BUDGET_GOAL_TYPE,
        category_code=None,
        target_amount=payload.monthly_budget,
        currency=payload.currency,
        period="monthly",
        starts_on=date.today(),
        is_active=True,
    )
    session.add(goal)
    await session.commit()
    await session.refresh(goal)
    return goal


@router.get("/budget/me", response_model=UserGoalRead)
async def get_my_budget(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserGoal:
    goal = await _active_monthly_budget(session, current_user.id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Monthly budget not set")
    return goal
