# Smoke-test endpoints only — no auth. TODO: add real authentication before
# this is exposed beyond local smoke testing.
#
# No PATCH/update endpoint by design: a biometric sample is an ingested
# wearable reading, not user-edited data.

import uuid
from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import PageParams, page_params
from wellness.api.errors import commit_or_409, not_found
from wellness.db import get_session
from wellness.models import BiometricSample
from wellness.schemas.samples import (
    SampleAverageBucket,
    SampleBatchResult,
    SampleCreate,
    SampleRead,
)

router = APIRouter(prefix="/samples", tags=["samples"])

_CONFLICT_KEY = (BiometricSample.user_id, BiometricSample.ts, BiometricSample.data_source)


@router.post("", response_model=SampleRead)
async def create_sample(
    payload: SampleCreate, response: Response, session: AsyncSession = Depends(get_session)
) -> BiometricSample:
    """The HealthKit shortcut resends overlapping readings — a duplicate
    (user_id, ts, data_source) is silently ignored (200 + the existing row),
    not a 409. Any other integrity violation (e.g. an unknown user_id) still
    surfaces normally.
    """
    stmt = (
        pg_insert(BiometricSample)
        .values(**payload.model_dump())
        .on_conflict_do_nothing(index_elements=_CONFLICT_KEY)
        .returning(BiometricSample)
    )
    try:
        result = await session.execute(stmt)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(exc.orig)) from exc

    inserted = result.scalars().one_or_none()
    if inserted is not None:
        await session.commit()
        response.status_code = 201
        return inserted

    await session.rollback()
    existing = (
        await session.execute(
            select(BiometricSample).where(
                BiometricSample.user_id == payload.user_id,
                BiometricSample.ts == payload.ts,
                BiometricSample.data_source == payload.data_source,
            )
        )
    ).scalar_one()
    response.status_code = 200
    return existing


@router.post("/batch", response_model=SampleBatchResult)
async def create_samples_batch(
    payload: Annotated[list[SampleCreate], Body(max_length=500)],
    session: AsyncSession = Depends(get_session),
) -> SampleBatchResult:
    received = len(payload)
    if received == 0:
        return SampleBatchResult(received=0, inserted=0, skipped=0)

    stmt = (
        pg_insert(BiometricSample)
        .values([sample.model_dump() for sample in payload])
        .on_conflict_do_nothing(index_elements=_CONFLICT_KEY)
        .returning(BiometricSample.id)
    )
    try:
        result = await session.execute(stmt)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(exc.orig)) from exc
    await session.commit()

    inserted = len(result.scalars().all())
    return SampleBatchResult(received=received, inserted=inserted, skipped=received - inserted)


@router.get("/averages", response_model=list[SampleAverageBucket])
async def get_sample_averages(
    user_id: uuid.UUID,
    period: Literal["day", "week", "month"],
    from_date: date | None = None,
    to_date: date | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[SampleAverageBucket]:
    bucket = sa_func.date_trunc(period, BiometricSample.ts).label("period_start")
    query = (
        select(
            bucket,
            sa_func.avg(BiometricSample.heart_rate),
            sa_func.min(BiometricSample.heart_rate),
            sa_func.max(BiometricSample.heart_rate),
            sa_func.count(BiometricSample.heart_rate),
        )
        .where(BiometricSample.user_id == user_id, BiometricSample.heart_rate.is_not(None))
        .group_by(bucket)
        .order_by(bucket)
    )
    if from_date is not None:
        query = query.where(BiometricSample.ts >= from_date)
    if to_date is not None:
        query = query.where(BiometricSample.ts < to_date + timedelta(days=1))

    rows = (await session.execute(query)).all()
    return [
        SampleAverageBucket(
            period_start=period_start,
            avg_heart_rate=avg_hr,
            min_heart_rate=min_hr,
            max_heart_rate=max_hr,
            count=count,
        )
        for period_start, avg_hr, min_hr, max_hr, count in rows
    ]


@router.get("", response_model=list[SampleRead])
async def list_samples(
    pagination: PageParams = Depends(page_params),
    session: AsyncSession = Depends(get_session),
) -> list[BiometricSample]:
    result = await session.execute(
        select(BiometricSample)
        .order_by(BiometricSample.ts.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    return list(result.scalars().all())


@router.get("/{sample_id}", response_model=SampleRead)
async def get_sample(
    sample_id: int, session: AsyncSession = Depends(get_session)
) -> BiometricSample:
    sample = await session.get(BiometricSample, sample_id)
    if sample is None:
        raise not_found("biometric_sample")
    return sample


@router.delete("/{sample_id}", status_code=204)
async def delete_sample(sample_id: int, session: AsyncSession = Depends(get_session)) -> None:
    sample = await session.get(BiometricSample, sample_id)
    if sample is None:
        raise not_found("biometric_sample")
    await session.delete(sample)
    await commit_or_409(session)
