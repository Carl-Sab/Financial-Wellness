"""Subjective pre-transaction check-ins.

Rows store either one direct arousal value (manual mode) or five separately
reported perceived inputs (detailed mode). The prediction adapter owns the
accepted proxy mapping from these perceived values to model feature names.
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
    category_code: Mapped[str] = mapped_column(
        Text, ForeignKey("categories.code"), nullable=False
    )
    valence: Mapped[ValenceLevel] = mapped_column(valence_level_enum, nullable=False)

    # Every arousal value is one of five discrete slider stops.
    arousal_input_mode: Mapped[str | None] = mapped_column(Text, nullable=True)
    arousal_z: Mapped[float | None] = mapped_column(REAL, nullable=True)
    perceived_heart_rate: Mapped[float | None] = mapped_column(REAL, nullable=True)
    perceived_heartbeat_steadiness: Mapped[float | None] = mapped_column(REAL, nullable=True)
    perceived_sweating: Mapped[float | None] = mapped_column(REAL, nullable=True)
    perceived_respiration: Mapped[float | None] = mapped_column(REAL, nullable=True)
    perceived_temperature_difference: Mapped[float | None] = mapped_column(REAL, nullable=True)

    entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "arousal_input_mode IS NULL OR arousal_input_mode IN ('manual', 'detailed')",
            name="arousal_input_mode_values",
        ),
        CheckConstraint(
            "(arousal_z IS NULL OR arousal_z IN (-2, -1, 0, 1, 2)) "
            "AND (perceived_heart_rate IS NULL "
            "OR perceived_heart_rate IN (-2, -1, 0, 1, 2)) "
            "AND (perceived_heartbeat_steadiness IS NULL "
            "OR perceived_heartbeat_steadiness IN (-2, -1, 0, 1, 2)) "
            "AND (perceived_sweating IS NULL "
            "OR perceived_sweating IN (-2, -1, 0, 1, 2)) "
            "AND (perceived_respiration IS NULL "
            "OR perceived_respiration IN (-2, -1, 0, 1, 2)) "
            "AND (perceived_temperature_difference IS NULL "
            "OR perceived_temperature_difference IN (-2, -1, 0, 1, 2))",
            name="arousal_values_discrete",
        ),
        CheckConstraint(
            "(arousal_input_mode IS NULL AND arousal_z IS NULL "
            "AND perceived_heart_rate IS NULL AND perceived_heartbeat_steadiness IS NULL "
            "AND perceived_sweating IS NULL AND perceived_respiration IS NULL "
            "AND perceived_temperature_difference IS NULL) "
            "OR (arousal_input_mode = 'manual' AND arousal_z IS NOT NULL "
            "AND perceived_heart_rate IS NULL AND perceived_heartbeat_steadiness IS NULL "
            "AND perceived_sweating IS NULL AND perceived_respiration IS NULL "
            "AND perceived_temperature_difference IS NULL) "
            "OR (arousal_input_mode = 'detailed' AND arousal_z IS NULL "
            "AND perceived_heart_rate IS NOT NULL "
            "AND perceived_heartbeat_steadiness IS NOT NULL "
            "AND perceived_sweating IS NOT NULL AND perceived_respiration IS NOT NULL "
            "AND perceived_temperature_difference IS NOT NULL)",
            name="arousal_input_contract",
        ),
        Index("ix_checkins_user_id_entered_at", "user_id", desc("entered_at")),
    )
