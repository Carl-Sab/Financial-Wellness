"""Versioned per-user normalization statistics.

Each row is a complete snapshot. Registration inserts the population defaults;
future personalization can append newer snapshots without changing history.
Prediction code must select the newest row for the user by recorded_at and id.
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
    desc,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from wellness.models.base import Base

POPULATION_NORMALIZATION_DEFAULTS: dict[str, float] = {
    # Physiological population statistics are prototype placeholders and are
    # not consumed by the current prediction flow.
    "heart_rate_mean": 0.0,
    "heart_rate_std": 0.0,
    "hrv_sdnn_mean": 0.0,
    "hrv_sdnn_std": 0.0,
    "skin_conductance_mean": 0.0,
    "skin_conductance_std": 0.0,
    "respiration_rate_mean": 0.0,
    "respiration_rate_std": 0.0,
    "skin_temperature_mean": 0.0,
    "skin_temperature_std": 0.0,
    # Population normalization bundled with the impulse model.
    "impulse_tendency_mean": 2.661558,
    "impulse_tendency_std": 0.831699,
    "self_control_mean": 3.037315,
    "self_control_std": 0.660859,
    "hedonic_mean": 4.636136363636,
    "hedonic_std": 1.022405590475,
    "utilitarian_mean": 4.276041666667,
    "utilitarian_std": 1.084810087389,
    "normative_evaluation_mean": 2.985884,
    "normative_evaluation_std": 0.660152,
}


class UserNormalizationSnapshot(Base):
    __tablename__ = "user_normalization_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    heart_rate_mean: Mapped[float] = mapped_column(REAL, nullable=False)
    heart_rate_std: Mapped[float] = mapped_column(REAL, nullable=False)
    hrv_sdnn_mean: Mapped[float] = mapped_column(REAL, nullable=False)
    hrv_sdnn_std: Mapped[float] = mapped_column(REAL, nullable=False)
    skin_conductance_mean: Mapped[float] = mapped_column(REAL, nullable=False)
    skin_conductance_std: Mapped[float] = mapped_column(REAL, nullable=False)
    respiration_rate_mean: Mapped[float] = mapped_column(REAL, nullable=False)
    respiration_rate_std: Mapped[float] = mapped_column(REAL, nullable=False)
    skin_temperature_mean: Mapped[float] = mapped_column(REAL, nullable=False)
    skin_temperature_std: Mapped[float] = mapped_column(REAL, nullable=False)

    impulse_tendency_mean: Mapped[float] = mapped_column(REAL, nullable=False)
    impulse_tendency_std: Mapped[float] = mapped_column(REAL, nullable=False)
    self_control_mean: Mapped[float] = mapped_column(REAL, nullable=False)
    self_control_std: Mapped[float] = mapped_column(REAL, nullable=False)
    hedonic_mean: Mapped[float] = mapped_column(REAL, nullable=False)
    hedonic_std: Mapped[float] = mapped_column(REAL, nullable=False)
    utilitarian_mean: Mapped[float] = mapped_column(REAL, nullable=False)
    utilitarian_std: Mapped[float] = mapped_column(REAL, nullable=False)
    normative_evaluation_mean: Mapped[float] = mapped_column(REAL, nullable=False)
    normative_evaluation_std: Mapped[float] = mapped_column(REAL, nullable=False)

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "heart_rate_std >= 0 AND hrv_sdnn_std >= 0 "
            "AND skin_conductance_std >= 0 AND respiration_rate_std >= 0 "
            "AND skin_temperature_std >= 0 AND impulse_tendency_std >= 0 "
            "AND self_control_std >= 0 AND hedonic_std >= 0 "
            "AND utilitarian_std >= 0 AND normative_evaluation_std >= 0",
            name="standard_deviations_non_negative",
        ),
        Index(
            "ix_user_normalization_snapshots_user_id_recorded_at",
            "user_id",
            desc("recorded_at"),
            desc("id"),
        ),
    )
