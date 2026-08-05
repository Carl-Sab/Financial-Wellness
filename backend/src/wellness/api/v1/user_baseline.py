# Read-only: user_baseline rows are written by the baseline-recompute
# service, not through the API.

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import PageParams, page_params
from wellness.api.errors import not_found
from wellness.db import get_session
from wellness.models import UserBaseline
from wellness.schemas.baseline import UserBaselineRead

router = APIRouter(prefix="/user-baseline", tags=["user_baseline"])


@router.get("", response_model=list[UserBaselineRead])
async def list_user_baselines(
    user_id: uuid.UUID | None = Query(default=None),
    pagination: PageParams = Depends(page_params),
    session: AsyncSession = Depends(get_session),
) -> list[UserBaseline]:
    query = select(UserBaseline).order_by(UserBaseline.user_id, UserBaseline.metric)
    if user_id is not None:
        query = query.where(UserBaseline.user_id == user_id)
    query = query.limit(pagination.limit).offset(pagination.offset)
    result = await session.execute(query)
    return list(result.scalars().all())


@router.get("/{user_id}/{metric}", response_model=UserBaselineRead)
async def get_user_baseline(
    user_id: uuid.UUID, metric: str, session: AsyncSession = Depends(get_session)
) -> UserBaseline:
    baseline = await session.get(UserBaseline, (user_id, metric))
    if baseline is None:
        raise not_found("user_baseline")
    return baseline
