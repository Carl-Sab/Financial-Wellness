"""Unified account movements and spending transactions.

Purchases are debit rows with a category and, optionally, a pre-purchase
check-in. Credits and account-only adjustments use the same table and may
leave category/check-in empty. Account balances and spending history therefore
come from one canonical set of rows.

The foreign keys are declared by table name so this spending-domain model does
not import the bank-account or check-in model modules.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    desc,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from wellness.models.base import Base
from wellness.models.enums import TransactionDirection

transaction_direction_enum = SAEnum(
    TransactionDirection,
    name="transaction_direction",
    native_enum=True,
    values_callable=lambda cls: [e.value for e in cls],
)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("bank_accounts.id"), nullable=False
    )
    checkin_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("checkins.id"), nullable=True
    )
    direction: Mapped[TransactionDirection] = mapped_column(
        transaction_direction_enum,
        nullable=False,
        default=TransactionDirection.DEBIT,
        server_default=TransactionDirection.DEBIT.value,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="LBP", server_default="LBP")
    category_code: Mapped[str | None] = mapped_column(
        Text, ForeignKey("categories.code"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        Index("ix_transactions_user_id_occurred_at", "user_id", desc("occurred_at")),
        Index("ix_transactions_account_id_occurred_at", "account_id", desc("occurred_at")),
        Index(
            "ix_transactions_user_id_category_code_occurred_at",
            "user_id",
            "category_code",
            desc("occurred_at"),
        ),
    )
