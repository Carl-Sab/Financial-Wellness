"""Manual physiological check-ins.

Arousal-scoring domain. Nothing here may import from wellness.models.transactions
or wellness.models.financial — see the boundary comment at the top of
transactions.py. Arousal is scored from physiology entered at a check-in,
compared against the user's own baseline; spending data plays no role in
that computation.

One row per pre-transaction check-in. Every physiological value is entered
by the user and all are nullable: the user may not have every reading
available, and a check-in with only some values is still useful. EEG is kept
because it was requested, but consumer wearables don't report it, so expect
it to be null in practice.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    REAL,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    desc,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from wellness.models.base import Base
from wellness.models.enums import ValenceLevel

# values_callable: see the note in categories.py — without it SQLAlchemy
# binds "NEUTRAL" instead of "neutral" and every insert fails.
valence_level_enum = SAEnum(
    ValenceLevel,
    name="valence_level",
    native_enum=True,
    values_callable=lambda cls: [e.value for e in cls],
)


class Checkin(Base):
    __tablename__ = "checkins"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category_code: Mapped[str] = mapped_column(Text, ForeignKey("categories.code"), nullable=False)
    valence: Mapped[ValenceLevel] = mapped_column(valence_level_enum, nullable=False)
    # 'pre_transaction' | 'standalone'
    checkin_type: Mapped[str] = mapped_column(
        Text, nullable=False, default="pre_transaction", server_default="pre_transaction"
    )

    heart_rate: Mapped[float | None] = mapped_column(REAL, nullable=True)
    hrv_ms: Mapped[float | None] = mapped_column(REAL, nullable=True)
    eda_microsiemens: Mapped[float | None] = mapped_column(REAL, nullable=True)
    spo2_percent: Mapped[float | None] = mapped_column(REAL, nullable=True)
    skin_temp_c: Mapped[float | None] = mapped_column(REAL, nullable=True)
    eeg_value: Mapped[float | None] = mapped_column(REAL, nullable=True)

    entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("heart_rate BETWEEN 30 AND 220", name="heart_rate_range"),
        CheckConstraint("hrv_ms BETWEEN 1 AND 300", name="hrv_ms_range"),
        CheckConstraint("eda_microsiemens BETWEEN 0 AND 100", name="eda_microsiemens_range"),
        CheckConstraint("spo2_percent BETWEEN 70 AND 100", name="spo2_percent_range"),
        CheckConstraint("skin_temp_c BETWEEN 30 AND 43", name="skin_temp_c_range"),
        CheckConstraint(
            "heart_rate IS NOT NULL OR hrv_ms IS NOT NULL OR eda_microsiemens IS NOT NULL "
            "OR spo2_percent IS NOT NULL OR skin_temp_c IS NOT NULL OR eeg_value IS NOT NULL",
            name="at_least_one_reading",
        ),
        Index("ix_checkins_user_id_entered_at", "user_id", desc("entered_at")),
    )
