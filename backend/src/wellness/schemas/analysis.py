from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class MoodSpendCorrelationItem(BaseModel):
    mood: str
    pearson_r: float | None
    p_value: float | None
    n: int


class MoodSpendCorrelationResponse(BaseModel):
    transaction_count: int
    correlations: list[MoodSpendCorrelationItem]
    scatter_plot_png_base64: str | None = None
    bar_chart_png_base64: str | None = None
    ai_report_markdown: str | None = None


class DailyBudget(BaseModel):
    amount: Decimal | None
    # 'goal_daily' | 'goal_monthly' | 'profile' | 'none'
    source: str


class MoodBucket(BaseModel):
    # 'stressed' | 'positive' | 'negative' | 'neutral' | 'unclassified'
    mood: str
    transaction_count: int
    overspend_count: int
    overspend_rate: float
    avg_amount: Decimal
    total_amount: Decimal


class MoodSpendingPeriod(BaseModel):
    period_start: date
    period_end: date
    buckets: list[MoodBucket]


class MoodSpendingResponse(BaseModel):
    daily_budget: DailyBudget
    periods: list[MoodSpendingPeriod]
    currency: str
