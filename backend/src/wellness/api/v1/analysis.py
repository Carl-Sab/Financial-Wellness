import base64
import math
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.analysis.mood_spend import (
    compute_correlations,
    compute_derived_columns,
    load_data,
    plot_results,
)
from wellness.analysis.report import generate_report
from wellness.api.deps import get_current_user
from wellness.config import get_settings
from wellness.db import get_session
from wellness.models import User
from wellness.schemas.analysis import (
    MoodSpendCorrelationItem,
    MoodSpendCorrelationResponse,
    MoodSpendingResponse,
)
from wellness.services.analysis import get_mood_spending_analysis

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _clean(value: float) -> float | None:
    return None if math.isnan(value) else value


@router.get("/mood-spend-correlation", response_model=MoodSpendCorrelationResponse)
async def get_mood_spend_correlation(
    include_ai_report: bool = Query(
        False, description="Also generate a written AI report (slower; requires API_KEY_SECRET_FROM_EURISKO)"
    ),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MoodSpendCorrelationResponse:
    """Pearson correlation between excess spend and mood/arousal, across the
    current user's linked-checkin transactions. See wellness/analysis/mood_spend.py.

    Used to run across all users at once (user_id omitted) — that
    aggregate mode is gone now that this requires auth; there's no admin
    role to scope it to.
    """
    raw_df = await load_data(session, current_user.id)
    if raw_df.empty:
        return MoodSpendCorrelationResponse(transaction_count=0, correlations=[])

    df = compute_derived_columns(raw_df)
    correlations = compute_correlations(df)
    items = [
        MoodSpendCorrelationItem(
            mood=row.mood, pearson_r=_clean(row.pearson_r), p_value=_clean(row.p_value), n=int(row.n)
        )
        for row in correlations.itertuples(index=False)
    ]

    with TemporaryDirectory() as tmpdir:
        scatter_path, bar_path = plot_results(df, correlations, Path(tmpdir))
        scatter_b64 = base64.b64encode(scatter_path.read_bytes()).decode()
        bar_b64 = base64.b64encode(bar_path.read_bytes()).decode()

        ai_report = None
        if include_ai_report and get_settings().gateway_api_key:
            ai_report = await generate_report(correlations, [scatter_path, bar_path])

    return MoodSpendCorrelationResponse(
        transaction_count=len(df),
        correlations=items,
        scatter_plot_png_base64=scatter_b64,
        bar_chart_png_base64=bar_b64,
        ai_report_markdown=ai_report,
    )


@router.get("/mood-spending", response_model=MoodSpendingResponse)
async def get_mood_spending(
    from_date: date,
    to_date: date,
    granularity: Literal["week", "month"],
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MoodSpendingResponse:
    """Overspend rate per mood bucket (stressed/positive/negative/neutral),
    broken into calendar week/month periods. See wellness/services/analysis.py.
    """
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must not be after to_date")
    return await get_mood_spending_analysis(
        session, current_user.id, from_date, to_date, granularity
    )
