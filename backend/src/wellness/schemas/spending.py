from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class SpendingWindow(BaseModel):
    period_start: date
    period_end: date
    spent: Decimal
    # None when no applicable all-categories goal exists. Daily and weekly
    # targets are normally derived by summing calendar-day allocations from
    # the active monthly budget.
    target: Decimal | None
    remaining: Decimal | None


class SpendingSummary(BaseModel):
    currency: str
    daily: SpendingWindow
    weekly: SpendingWindow
    monthly: SpendingWindow
    balance: Decimal
