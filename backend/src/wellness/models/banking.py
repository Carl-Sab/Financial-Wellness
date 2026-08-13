"""Bank accounts used by the unified transaction history.

An account stores only its opening balance. Its current balance is derived
from credit/debit rows in ``transactions``; there is no separate ledger table
and no mutable current-balance column that can drift out of sync.

This module stays independent of the check-in domain. The transaction model
resolves its account foreign key by table name through shared SQLAlchemy
metadata, so the model modules do not need to import one another.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from wellness.models.base import Base


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    account_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="LBP", server_default="LBP")
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
