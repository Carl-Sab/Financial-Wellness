import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TransactionCreate(BaseModel):
    user_id: uuid.UUID
    checkin_id: int | None = None
    amount: Decimal = Field(ge=0)
    currency: str = "LBP"
    category_code: str
    merchant_name: str | None = None
    occurred_at: datetime | None = None
    was_planned: bool | None = None


class TransactionUpdate(BaseModel):
    checkin_id: int | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = None
    category_code: str | None = None
    merchant_name: str | None = None
    occurred_at: datetime | None = None
    was_planned: bool | None = None


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: uuid.UUID
    checkin_id: int | None
    amount: Decimal
    currency: str
    category_code: str
    merchant_name: str | None
    occurred_at: datetime
    was_planned: bool | None
    created_at: datetime
