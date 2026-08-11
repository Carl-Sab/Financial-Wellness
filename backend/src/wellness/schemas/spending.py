from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class SpendingWindow(BaseModel):
    period_start: date
    period_end: date
    spent: Decimal
    # None when no active, all-categories goal exists for this period —
    # onboarding only ever creates a monthly one, so daily/weekly normally
    # have no target. That's expected, not an error.
    target: Decimal | None
    remaining: Decimal | None


class SpendingSummary(BaseModel):
    currency: str
    daily: SpendingWindow
    weekly: SpendingWindow
    monthly: SpendingWindow
    balance: Decimal
