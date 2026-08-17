from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import PageParams, get_current_user, page_params
from wellness.api.errors import commit_or_409, not_found
from wellness.db import get_session
from wellness.models import Checkin, User
from wellness.schemas.checkins import CheckinCreate, CheckinRead, CheckinUpdate
from wellness.schemas.predictions import CheckinPredictionRead
from wellness.services.notifications import notify_checkin_risk
from wellness.services.prediction import predict_checkin

router = APIRouter(prefix="/checkins", tags=["checkins"])


@router.post("", response_model=CheckinRead, status_code=201)
async def create_checkin(
    payload: CheckinCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Checkin:
    checkin = Checkin(**payload.model_dump(), user_id=current_user.id)
    session.add(checkin)
    await commit_or_409(session)
    await session.refresh(checkin)

    return checkin


@router.get("", response_model=list[CheckinRead])
async def list_checkins(
    pagination: PageParams = Depends(page_params),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Checkin]:
    result = await session.execute(
        select(Checkin)
        .where(Checkin.user_id == current_user.id)
        .order_by(Checkin.entered_at.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    return list(result.scalars().all())


@router.get("/{checkin_id}", response_model=CheckinRead)
async def get_checkin(
    checkin_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Checkin:
    checkin = await session.get(Checkin, checkin_id)
    if checkin is None or checkin.user_id != current_user.id:
        raise not_found("checkin")
    return checkin


@router.post("/{checkin_id}/prediction", response_model=CheckinPredictionRead)
async def create_checkin_prediction(
    checkin_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CheckinPredictionRead:
    # Imported here to keep the v1 package's router assembly from creating a
    # circular import between this sibling module and spending.py.
    from wellness.api.v1.spending import build_spending_summary

    checkin = await session.get(Checkin, checkin_id)
    if checkin is None or checkin.user_id != current_user.id:
        raise not_found("checkin")
    spending = await build_spending_summary(session, current_user)
    prediction = await predict_checkin(session, current_user, checkin, spending)
    await notify_checkin_risk(
        session,
        current_user,
        checkin.id,
        prediction.risk_level,
        prediction.arousal_z,
    )
    return prediction


@router.patch("/{checkin_id}", response_model=CheckinRead)
async def update_checkin(
    checkin_id: int,
    payload: CheckinUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Checkin:
    checkin = await session.get(Checkin, checkin_id)
    if checkin is None or checkin.user_id != current_user.id:
        raise not_found("checkin")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(checkin, key, value)
    await commit_or_409(session)
    await session.refresh(checkin)
    return checkin


@router.delete("/{checkin_id}", status_code=204)
async def delete_checkin(
    checkin_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    checkin = await session.get(Checkin, checkin_id)
    if checkin is None or checkin.user_id != current_user.id:
        raise not_found("checkin")
    await session.delete(checkin)
    await commit_or_409(session)
