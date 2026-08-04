import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class UserGoalCreate(BaseModel):
    user_id: uuid.UUID
    goal_type: str
    category_code: str | None = None
    target_amount: Decimal = Field(gt=0)
    period: str
    starts_on: date
    ends_on: date | None = None
    is_active: bool = True


class UserGoalUpdate(BaseModel):
    goal_type: str | None = None
    category_code: str | None = None
    target_amount: Decimal | None = Field(default=None, gt=0)
    period: str | None = None
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
