"""User-defined spending goals.

ARCHITECTURAL BOUNDARY: nothing in this module may be imported by, or import
from, wellness.models.checkins, wellness.models.baseline, or
wellness.models.arousal (the arousal-scoring domain). See the boundary
comment at the top of transactions.py for the full rationale.

Progress toward a goal is never cached here: no current_spent column. It is
always computed by summing transactions in the goal's period at read time,
the same way bank_accounts balances are always summed from bank_ledger
rather than stored — see the boundary comment in banking.py.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from wellness.models.base import Base


class UserGoal(Base):
    __tablename__ = "user_goals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # 'monthly_budget' | 'category_cap'
    goal_type: Mapped[str] = mapped_column(Text, nullable=False)
    # Null means the goal applies across all categories.
    category_code: Mapped[str | None] = mapped_column(
        Text, ForeignKey("categories.code"), nullable=True
    )
    target_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # 'LBP' | 'USD' — see wellness.services.currency for the fixed conversion
    # rate used when comparing against transactions in the other currency.
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="LBP", server_default="LBP")
    # 'weekly' | 'monthly' | 'daily'
    period: Mapped[str] = mapped_column(Text, nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("target_amount > 0", name="target_amount_positive"),
        Index("ix_user_goals_user_id_active", "user_id", postgresql_where=text("is_active")),
    )
