import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GoalPeriod = Literal["weekly", "monthly", "daily"]


GoalCurrency = Literal["LBP", "USD"]


class UserGoalCreate(BaseModel):
    goal_type: str
    category_code: str | None = None
    target_amount: Decimal = Field(gt=0)
    currency: GoalCurrency = "LBP"
    period: GoalPeriod
    starts_on: date
    ends_on: date | None = None
    is_active: bool = True


class UserGoalUpdate(BaseModel):
    goal_type: str | None = None
    category_code: str | None = None
    target_amount: Decimal | None = Field(default=None, gt=0)
    currency: GoalCurrency | None = None
    period: GoalPeriod | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    is_active: bool | None = None


class UserGoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: uuid.UUID
    goal_type: str
    category_code: str | None
    target_amount: Decimal
    currency: str
    period: str
    starts_on: date
    ends_on: date | None
    is_active: bool
    created_at: datetime


class GoalProgress(BaseModel):
    goal_id: int
    period_start: date
    period_end: date
    target_amount: Decimal
    spent_amount: Decimal
    remaining_amount: Decimal


class MonthlyGoalProgress(BaseModel):
    target_amount: Decimal
    spent_amount: Decimal
    remaining_amount: Decimal
    is_over: bool
    overage_amount: Decimal


MonthlySuggestionBasis = Literal["reduce_from_overspend", "tighten_from_underspend"]


class MonthlySuggestion(BaseModel):
    amount: Decimal
    currency: GoalCurrency
    basis: MonthlySuggestionBasis


MonthlyGoalStatusValue = Literal["active", "needs_setup"]


class MonthlyGoalStatus(BaseModel):
    status: MonthlyGoalStatusValue
    goal: UserGoalRead | None = None
    progress: MonthlyGoalProgress | None = None
    suggestion: MonthlySuggestion | None = None


class MonthlyGoalSubmit(BaseModel):
    target_amount: Decimal | None = Field(default=None, gt=0)
    currency: GoalCurrency = "LBP"
    accept_suggestion: bool = False
