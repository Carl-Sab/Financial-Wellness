from decimal import Decimal

from pydantic import BaseModel, Field


class BudgetSubmitRequest(BaseModel):
    # gt=0, not ge=0: a zero budget makes every purchase an overspend,
    # which is noise, not signal.
    monthly_budget: Decimal = Field(gt=0)
