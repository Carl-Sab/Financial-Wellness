"""Derived arousal state, one row per check-in.

Arousal-scoring domain. Nothing here may import from wellness.models.transactions
or wellness.models.financial — see the boundary comment at the top of
transactions.py. Arousal is computed by comparing a check-in's readings to
the user's baseline; spending data plays no role in that computation.
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
    SmallInteger,
    Text,
    desc,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from wellness.models.base import Base
from wellness.models.enums import ArousalLabel

# values_callable: see the note in categories.py — without it SQLAlchemy
# binds the member name ("UNKNOWN") instead of its value ("unknown").
arousal_label_enum = SAEnum(
    ArousalLabel,
    name="arousal_label",
    native_enum=True,
    values_callable=lambda cls: [e.value for e in cls],
)


class ArousalState(Base):
    __tablename__ = "arousal_state"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    checkin_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("checkins.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Per-metric z-scores: (reading - user mean) / user sd.
    z_heart_rate: Mapped[float | None] = mapped_column(REAL, nullable=True)
    z_hrv: Mapped[float | None] = mapped_column(REAL, nullable=True)
    z_eda: Mapped[float | None] = mapped_column(REAL, nullable=True)
    z_spo2: Mapped[float | None] = mapped_column(REAL, nullable=True)
    z_skin_temp: Mapped[float | None] = mapped_column(REAL, nullable=True)

    score: Mapped[float | None] = mapped_column(REAL, nullable=True)
    label: Mapped[ArousalLabel] = mapped_column(
        arousal_label_enum,
        nullable=False,
        default=ArousalLabel.UNKNOWN,
        server_default=ArousalLabel.UNKNOWN.value,
    )
    confidence: Mapped[float | None] = mapped_column(REAL, nullable=True)
    metrics_used: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # Total biometric_samples rows behind the metrics that were window-sourced
    # (0 when none were — every reading came from the typed check-in).
    window_sample_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )
    # 'samples' if at least one metric's reading came from the biometric_samples
    # 15-minute window average, 'checkins' if every reading was typed in.
    reading_source: Mapped[str] = mapped_column(
        Text, nullable=False, default="checkins", server_default="checkins"
    )
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 1", name="score_range"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
        Index("ix_arousal_state_user_id_computed_at", "user_id", desc("computed_at")),
    )
