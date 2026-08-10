"""Wearable-sourced biometric samples (e.g. Apple HealthKit).

Arousal-scoring domain. Nothing here may import from wellness.models.transactions,
wellness.models.financial, wellness.models.banking, or wellness.models.goals —
see the boundary comment at the top of wellness.models.transactions.

Distinct from checkins: a checkin is a single manually-entered reading tied to
a spending decision; a biometric sample is background wearable data, ingested
in bulk on its own schedule, with no transaction context. refresh_baseline()
prefers samples over checkins once a user has at least 30 samples for a
metric, and score_checkin() prefers the 15-minute-window sample average over
the typed check-in value when the window has at least 3 samples — see
wellness.services.baseline and wellness.services.arousal.
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
    UniqueConstraint,
    desc,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from wellness.models.base import Base


class BiometricSample(Base):
    __tablename__ = "biometric_samples"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # When the reading was taken, not when it was ingested.
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    heart_rate: Mapped[float | None] = mapped_column(REAL, nullable=True)
    hrv_ms: Mapped[float | None] = mapped_column(REAL, nullable=True)
    spo2_percent: Mapped[float | None] = mapped_column(REAL, nullable=True)

    data_source: Mapped[str] = mapped_column(
        Text, nullable=False, default="healthkit", server_default="healthkit"
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("heart_rate BETWEEN 30 AND 220", name="heart_rate_range"),
        CheckConstraint("hrv_ms BETWEEN 1 AND 300", name="hrv_ms_range"),
        CheckConstraint("spo2_percent BETWEEN 70 AND 100", name="spo2_percent_range"),
        CheckConstraint(
            "heart_rate IS NOT NULL OR hrv_ms IS NOT NULL OR spo2_percent IS NOT NULL",
            name="at_least_one_reading",
        ),
        UniqueConstraint(
            "user_id", "ts", "data_source", name="uq_biometric_samples_user_id_ts_data_source"
        ),
        Index("ix_biometric_samples_user_id_ts", "user_id", desc("ts")),
    )
