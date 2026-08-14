from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import get_current_user
from wellness.db import get_session
from wellness.models import User
from wellness.schemas.analysis import (
    CategoryView,
    CorrelationSummaryRequest,
    CorrelationSummaryResponse,
    StatisticsResponse,
    StatisticsView,
)
from wellness.services.analysis import get_statistics
from wellness.services.correlation_feedback import get_correlation_summary

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/statistics", response_model=StatisticsResponse)
async def statistics(
    view: StatisticsView = Query("weekly"),
    anchor: date = Query(default_factory=date.today),
    category_view: CategoryView = Query("yearly"),
    category_anchor: date = Query(default_factory=date.today),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StatisticsResponse:
    """Return the selected spending review, daily weighted mood points,
    and an independently selected category summary for the signed-in user.
    """

    return await get_statistics(
        session=session,
        user_id=current_user.id,
        display_currency=current_user.currency,
        user_timezone=current_user.timezone,
        view=view,
        anchor=anchor,
        category_view=category_view,
        category_anchor=category_anchor,
    )


@router.post("/correlation-summary", response_model=CorrelationSummaryResponse)
async def correlation_summary(
    payload: CorrelationSummaryRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CorrelationSummaryResponse:
    """Describe the three relationship charts using verified daily points."""

    return await get_correlation_summary(
        session=session,
        user_id=current_user.id,
        display_currency=current_user.currency,
        user_timezone=current_user.timezone,
        view=payload.view,
        anchor=payload.anchor,
    )
