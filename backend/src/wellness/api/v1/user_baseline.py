# Read-only: user_baseline rows are written by the baseline-recompute
# service, not through the API.

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import PageParams, get_current_user, page_params
from wellness.api.errors import not_found
from wellness.db import get_session
from wellness.models import User, UserBaseline
from wellness.schemas.baseline import UserBaselineRead

router = APIRouter(prefix="/user-baseline", tags=["user_baseline"])


@router.get("", response_model=list[UserBaselineRead])
async def list_user_baselines(
    pagination: PageParams = Depends(page_params),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[UserBaseline]:
    query = (
        select(UserBaseline)
        .where(UserBaseline.user_id == current_user.id)
        .order_by(UserBaseline.metric)
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    result = await session.execute(query)
    return list(result.scalars().all())


@router.get("/{metric}", response_model=UserBaselineRead)
async def get_user_baseline(
    metric: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserBaseline:
    baseline = await session.get(UserBaseline, (current_user.id, metric))
    if baseline is None:
        raise not_found("user_baseline")
    return baseline
