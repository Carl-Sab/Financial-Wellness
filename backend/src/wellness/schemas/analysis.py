from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

StatisticsView = Literal["weekly", "monthly", "yearly"]
CategoryView = Literal["daily", "weekly", "monthly", "yearly"]
CorrelationMetric = Literal["positive_mood", "negative_mood", "arousal"]
CorrelationClassification = Literal[
    "insufficient_data",
    "no_clear_pattern",
    "possible_positive_pattern",
    "possible_negative_pattern",
    "clear_positive_pattern",
    "clear_negative_pattern",
]


class StatisticsBudget(BaseModel):
    monthly_amount: Decimal | None
    starts_on: date | None


class SpendingReviewBucket(BaseModel):
    label: str
    period_start: date
    period_end: date
    spent_amount: Decimal
    budget_amount: Decimal
    normalized_spending: float | None
    overspent: bool | None
    transaction_count: int


class DailyMoodPoint(BaseModel):
    day: date
    positive_mood: float
    negative_mood: float
    arousal: float | None
    normalized_spending: float
    spent_amount: Decimal
    transaction_count: int
    checkin_transaction_count: int
    checkin_spend_coverage: float


class CategorySpendingItem(BaseModel):
    category_code: str | None
    label: str
    spent_amount: Decimal
    share: float


class CategorySummary(BaseModel):
    view: CategoryView
    range_start: date
    range_end: date
    total_spent: Decimal
    allocated_budget: Decimal
    categories: list[CategorySpendingItem]


class StatisticsResponse(BaseModel):
    view: StatisticsView
    range_start: date
    range_end: date
    currency: str
    budget: StatisticsBudget
    review: list[SpendingReviewBucket]
    daily_mood: list[DailyMoodPoint]
    category_summary: CategorySummary


class CorrelationSummaryRequest(BaseModel):
    view: StatisticsView = "weekly"
    anchor: date


class CorrelationResult(BaseModel):
    metric: CorrelationMetric
    coefficient: float | None
    p_value: float | None
    days_analyzed: int
    classification: CorrelationClassification


class CorrelationSummaryText(BaseModel):
    overall: str
    positive_mood: str
    negative_mood: str
    arousal: str
    data_note: str


class CorrelationSummaryResponse(BaseModel):
    range_start: date
    range_end: date
    correlations: list[CorrelationResult]
    summary: CorrelationSummaryText
    source: Literal["ai", "template"]
