"""Bank accounts and their ledger.

ARCHITECTURAL BOUNDARY: nothing in this module may be imported by, or import
from, wellness.models.checkins, wellness.models.baseline, or
wellness.models.arousal (the arousal-scoring domain). See the boundary
comment at the top of transactions.py for the full rationale.

Account balance is never stored as a column. It is always derived by summing
the ledger:

    SELECT COALESCE(SUM(CASE direction WHEN 'credit' THEN amount
                                        ELSE -amount END), 0)
    FROM bank_ledger WHERE account_id = :id;

bank_ledger.transaction_id below is a plain foreign-key column (not an ORM
relationship) so this module never needs to import wellness.models.transactions
— SQLAlchemy resolves the FK target by table name against the shared
Base.metadata.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    desc,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from wellness.models.base import Base
from wellness.models.enums import LedgerDirection

# values_callable: see the note in categories.py — without it SQLAlchemy
# binds the member name ("CREDIT") instead of its value ("credit").
ledger_direction_enum = SAEnum(
    LedgerDirection,
    name="ledger_direction",
    native_enum=True,
    values_callable=lambda cls: [e.value for e in cls],
)


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    account_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="LBP", server_default="LBP")
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BankLedger(Base):
    __tablename__ = "bank_ledger"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[LedgerDirection] = mapped_column(ledger_direction_enum, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # No ON DELETE action: a transaction must not be deletable out from under
    # a ledger entry.
    transaction_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("transactions.id"), nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_bank_ledger_account_id_occurred_at", "account_id", desc("occurred_at")),
    )
