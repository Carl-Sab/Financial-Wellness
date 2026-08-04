import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from wellness.models.enums import LedgerDirection


class BankAccountCreate(BaseModel):
    user_id: uuid.UUID
    account_number: str
    currency: str = "LBP"
    is_active: bool = True


class BankAccountUpdate(BaseModel):
    account_number: str | None = None
    currency: str | None = None
    is_active: bool | None = None


class BankAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: uuid.UUID
    account_number: str
    currency: str
    is_active: bool
    opened_at: datetime


class BankAccountBalance(BaseModel):
    account_id: int
    balance: Decimal


class BankLedgerCreate(BaseModel):
    account_id: int
    direction: LedgerDirection
    amount: Decimal = Field(gt=0)
    description: str | None = None
    transaction_id: int | None = None


class BankLedgerUpdate(BaseModel):
    direction: LedgerDirection | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    description: str | None = None
    transaction_id: int | None = None


class BankLedgerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    direction: LedgerDirection
    amount: Decimal
    description: str | None
    transaction_id: int | None
    occurred_at: datetime
