"""Spending transactions.

ARCHITECTURAL BOUNDARY: nothing in this module may be imported by, or import
from, wellness.models.checkins, wellness.models.baseline, or
wellness.models.arousal (the arousal-scoring domain). Arousal is scored on
physiology alone, relative to the user's own baseline; financial data plays
no role in that computation. Spending is analysed against arousal, never
used to produce it. Keeping these domains in separate modules with no import
path between them makes that boundary visible to anyone reading the code,
and any accidental coupling shows up immediately as a new, out-of-place
import.

checkin_id below is a plain foreign-key column (not an ORM relationship) so
this module never needs to import wellness.models.checkins — SQLAlchemy
resolves the FK target by table name against the shared Base.metadata.
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
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from wellness.models.base import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # The check-in that preceded this transaction, if any. No ON DELETE
    # action: a checkin must not be deletable out from under a transaction.
    checkin_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("checkins.id"), nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="LBP", server_default="LBP")
    category_code: Mapped[str] = mapped_column(Text, ForeignKey("categories.code"), nullable=False)
    merchant_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    was_planned: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        Index("ix_transactions_user_id_occurred_at", "user_id", desc("occurred_at")),
        Index(
            "ix_transactions_user_id_category_code_occurred_at",
            "user_id",
            "category_code",
            desc("occurred_at"),
        ),
    )
