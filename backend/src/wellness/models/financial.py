"""Financial reporting data.

ARCHITECTURAL BOUNDARY: nothing in this module may be imported by, or import
from, wellness.models.biometrics (or any future arousal-scoring code). Arousal
is scored on physiology alone — heart rate, HRV, EDA, respiration, skin temp —
relative to the user's own baseline. Financial data plays no role in that
computation; it exists solely for user-facing reporting. Keeping these two
domains in separate modules with no import path between them makes that
boundary visible to anyone reading the code, and any accidental coupling shows
up immediately as a new, out-of-place import.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from wellness.models.base import Base, new_uuid


class FinancialProfile(Base):
    """Versioned financial snapshot. Never updated in place: a change closes the
    current row (sets valid_to) and inserts a new one with valid_from set and
    valid_to null. The current profile for a user is the row with valid_to IS NULL.
    """

    __tablename__ = "financial_profile"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    monthly_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    avg_monthly_spend: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fixed_costs: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
