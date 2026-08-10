# Smoke-test endpoints only — no auth. TODO: add real authentication before
# this is exposed beyond local smoke testing.

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import PageParams, page_params
from wellness.api.errors import commit_or_409, not_found
from wellness.db import get_session
from wellness.models import ArousalState, Checkin
from wellness.schemas.arousal import ArousalStateRead
from wellness.schemas.checkins import CheckinCreate, CheckinRead, CheckinUpdate
from wellness.services.arousal import score_checkin
from wellness.services.baseline import refresh_baseline

router = APIRouter(prefix="/checkins", tags=["checkins"])
logger = structlog.get_logger(__name__)


@router.post("", response_model=CheckinRead, status_code=201)
async def create_checkin(
    payload: CheckinCreate, session: AsyncSession = Depends(get_session)
) -> Checkin:
    checkin = Checkin(**payload.model_dump())
    session.add(checkin)
    await commit_or_409(session)
    await session.refresh(checkin)

    # A scoring failure must never lose the check-in that was just committed
    # above — log and move on, the check-in response below still succeeds.
    try:
        await refresh_baseline(session, checkin.user_id)
        await score_checkin(session, checkin.id)
    except Exception:
        await session.rollback()
        logger.error("checkin_scoring_failed", checkin_id=checkin.id, exc_info=True)

    return checkin


@router.get("", response_model=list[CheckinRead])
async def list_checkins(
    pagination: PageParams = Depends(page_params),
    session: AsyncSession = Depends(get_session),
) -> list[Checkin]:
    result = await session.execute(
        select(Checkin)
        .order_by(Checkin.entered_at.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    return list(result.scalars().all())


@router.get("/{checkin_id}", response_model=CheckinRead)
async def get_checkin(checkin_id: int, session: AsyncSession = Depends(get_session)) -> Checkin:
    checkin = await session.get(Checkin, checkin_id)
    if checkin is None:
        raise not_found("checkin")
    return checkin


@router.get("/{checkin_id}/arousal", response_model=ArousalStateRead)
async def get_checkin_arousal(
    checkin_id: int, session: AsyncSession = Depends(get_session)
) -> ArousalState:
    result = await session.execute(
        select(ArousalState).where(ArousalState.checkin_id == checkin_id)
    )
    arousal_state = result.scalar_one_or_none()
    if arousal_state is None:
        raise not_found("arousal_state")
    return arousal_state


@router.patch("/{checkin_id}", response_model=CheckinRead)
async def update_checkin(
    checkin_id: int, payload: CheckinUpdate, session: AsyncSession = Depends(get_session)
) -> Checkin:
    checkin = await session.get(Checkin, checkin_id)
    if checkin is None:
        raise not_found("checkin")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(checkin, key, value)
    await commit_or_409(session)
    await session.refresh(checkin)
    return checkin


@router.delete("/{checkin_id}", status_code=204)
async def delete_checkin(checkin_id: int, session: AsyncSession = Depends(get_session)) -> None:
    checkin = await session.get(Checkin, checkin_id)
    if checkin is None:
        raise not_found("checkin")
    await session.delete(checkin)
    await commit_or_409(session)
