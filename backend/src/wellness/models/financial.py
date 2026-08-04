"""Financial reporting data.

ARCHITECTURAL BOUNDARY: nothing in this module may be imported by, or import
from, wellness.models.checkins, wellness.models.baseline, or
wellness.models.arousal (the arousal-scoring domain). See the boundary
comment at the top of transactions.py for the full rationale.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from wellness.models.base import Base


class FinancialProfile(Base):
    """Versioned financial snapshot. Never updated in place: a change closes
    the current row (sets valid_to) and inserts a new one with valid_from set
    and valid_to null. The current profile for a user is the row with
    valid_to IS NULL — enforced by the partial unique index below.
    """

    __tablename__ = "financial_profile"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    monthly_income: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    avg_monthly_spend: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="LBP", server_default="LBP")
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "one_current_financial_profile",
            "user_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )
