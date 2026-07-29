"""Physiology and arousal-scoring data.

Nothing here may import from wellness.models.financial — see the boundary
comment at the top of that module. Arousal is derived from physiology and each
user's own baseline only.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from wellness.models.base import Base, new_uuid
from wellness.models.enums import ArousalLabel, BiometricQualityFlag


class BiometricSample(Base):
    """Hypertable, one wide row per timestamp per user. Not every device reports
    every metric, so all metric columns are nullable — but at least one must be
    present (see the check constraint below).
    """

    __tablename__ = "biometric_samples"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), default=new_uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    hr: Mapped[float | None] = mapped_column(Float, nullable=True)
    hrv_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    eda_microsiemens: Mapped[float | None] = mapped_column(Float, nullable=True)
    respiration_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    skin_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)

    source_device: Mapped[str] = mapped_column(String(120), nullable=False)
    quality_flag: Mapped[BiometricQualityFlag] = mapped_column(
        SAEnum(BiometricQualityFlag, name="biometric_quality_flag", native_enum=True),
        nullable=False,
        default=BiometricQualityFlag.OK,
        server_default=BiometricQualityFlag.OK.value,
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # Partition key (user_id, ts): user_id first so the PK's leading edge
        # matches Timescale's space partition, ts second for the time dimension,
        # id last only to disambiguate same-timestamp rows from different devices.
        PrimaryKeyConstraint("user_id", "ts", "id", name="pk_biometric_samples"),
        CheckConstraint(
            "hr IS NOT NULL OR hrv_ms IS NOT NULL OR eda_microsiemens IS NOT NULL "
            "OR respiration_rate IS NOT NULL OR skin_temp_c IS NOT NULL",
            name="at_least_one_metric_present",
        ),
    )


class ArousalState(Base):
    """Hypertable. Lower frequency than biometric_samples — one row per scoring run."""

    __tablename__ = "arousal_state"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), default=new_uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    score: Mapped[float] = mapped_column(Float, nullable=False)
    label: Mapped[ArousalLabel] = mapped_column(
        SAEnum(ArousalLabel, name="arousal_label", native_enum=True), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input_window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "ts", "id", name="pk_arousal_state"),
        CheckConstraint("score >= 0 AND score <= 1", name="score_between_0_and_1"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_between_0_and_1"),
    )


class UserBaseline(Base):
    """Per user, per metric rolling baseline (median + MAD), recomputed nightly
    and read cheaply at scoring time. Overwritten in place — one current row per
    (user_id, metric_name).
    """

    __tablename__ = "user_baseline"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # One of: hr, hrv_ms, eda_microsiemens, respiration_rate, skin_temp_c.
    metric_name: Mapped[str] = mapped_column(String(32), nullable=False)
    rolling_median: Mapped[float] = mapped_column(Float, nullable=False)
    rolling_mad: Mapped[float] = mapped_column(Float, nullable=False)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "metric_name", name="uq_user_baseline_user_metric"),
    )
