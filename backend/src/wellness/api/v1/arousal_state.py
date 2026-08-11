# Read-only: arousal_state rows are written by the arousal-scoring service,
# not through the API.

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import PageParams, get_current_user, page_params
from wellness.api.errors import not_found
from wellness.db import get_session
from wellness.models import ArousalState, User
from wellness.schemas.arousal import ArousalStateRead

router = APIRouter(prefix="/arousal-state", tags=["arousal_state"])


@router.get("", response_model=list[ArousalStateRead])
async def list_arousal_states(
    pagination: PageParams = Depends(page_params),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ArousalState]:
    result = await session.execute(
        select(ArousalState)
        .where(ArousalState.user_id == current_user.id)
        .order_by(ArousalState.computed_at.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    return list(result.scalars().all())


@router.get("/{state_id}", response_model=ArousalStateRead)
async def get_arousal_state(
    state_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ArousalState:
    state = await session.get(ArousalState, state_id)
    if state is None or state.user_id != current_user.id:
        raise not_found("arousal_state")
    return state
