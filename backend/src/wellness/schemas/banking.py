import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class BankAccountCreate(BaseModel):
    account_number: str
    currency: str = "LBP"
    opening_balance: Decimal = Decimal("0")
    is_active: bool = True


class BankAccountUpdate(BaseModel):
    account_number: str | None = None
    currency: str | None = None
    opening_balance: Decimal | None = None
    is_active: bool | None = None


class BankAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: uuid.UUID
    account_number: str
    currency: str
    opening_balance: Decimal
    is_active: bool
    opened_at: datetime


class BankAccountBalance(BaseModel):
    account_id: int
    balance: Decimal
