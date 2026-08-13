import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from wellness.models.enums import TransactionDirection


class TransactionCreate(BaseModel):
    # Optional for compatibility with the single-account UI. The backend
    # resolves the user's oldest active account when this is omitted.
    account_id: int | None = None
    checkin_id: int | None = None
    direction: TransactionDirection = TransactionDirection.DEBIT
    amount: Decimal = Field(ge=0)
    currency: str | None = None
    category_code: str | None = None
    description: str | None = None
    occurred_at: datetime | None = None


class TransactionUpdate(BaseModel):
    account_id: int | None = None
    checkin_id: int | None = None
    direction: TransactionDirection | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = None
    category_code: str | None = None
    description: str | None = None
    occurred_at: datetime | None = None


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: uuid.UUID
    account_id: int
    checkin_id: int | None
    direction: TransactionDirection
    amount: Decimal
    currency: str
    category_code: str | None
    description: str | None
    occurred_at: datetime
    created_at: datetime
