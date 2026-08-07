# Smoke-test endpoints only — no auth. TODO: add real authentication before
# this is exposed beyond local smoke testing.

import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.db import get_session
from wellness.schemas.analysis import MoodSpendingResponse
from wellness.services.analysis import get_mood_spending_analysis

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/mood-spending", response_model=MoodSpendingResponse)
async def get_mood_spending(
    user_id: uuid.UUID,
    from_date: date,
    to_date: date,
    granularity: Literal["week", "month"],
    session: AsyncSession = Depends(get_session),
) -> MoodSpendingResponse:
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must not be after to_date")
    return await get_mood_spending_analysis(session, user_id, from_date, to_date, granularity)
