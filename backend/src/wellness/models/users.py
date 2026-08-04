import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    REAL,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Text,
    desc,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from wellness.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(
        Text, nullable=False, default="Asia/Beirut", server_default="Asia/Beirut"
    )
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="LBP", server_default="LBP")
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Age is derived, never stored - it would go stale:
    #   SELECT date_part('year', age(date_of_birth)) FROM users;


class QuestionnaireResponse(Base):
    """Signup questionnaire: four trait-framed scales, administered once.

    Raw item responses are kept alongside the computed scores so the scores
    can be recomputed or checked for reliability later.
    """

    __tablename__ = "questionnaire_responses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Rook & Fisher (1995), 9 items, 1-5
    impulse_tendency_score: Mapped[float | None] = mapped_column(REAL, nullable=True)
    # Tangney et al. (2004), 13 items, 1-5
    self_control_score: Mapped[float | None] = mapped_column(REAL, nullable=True)
    # Babin et al. (1994) adapted to trait framing, 11 items, 1-7
    hedonic_score: Mapped[float | None] = mapped_column(REAL, nullable=True)
    # Babin et al. (1994) adapted to trait framing, 4 items, 1-7
    utilitarian_score: Mapped[float | None] = mapped_column(REAL, nullable=True)

    raw_responses: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    instrument_version: Mapped[str] = mapped_column(
        Text, nullable=False, default="v1", server_default="v1"
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "impulse_tendency_score BETWEEN 1 AND 5", name="impulse_tendency_score_range"
        ),
        CheckConstraint("self_control_score BETWEEN 1 AND 5", name="self_control_score_range"),
        CheckConstraint("hedonic_score BETWEEN 1 AND 7", name="hedonic_score_range"),
        CheckConstraint("utilitarian_score BETWEEN 1 AND 7", name="utilitarian_score_range"),
        Index("ix_questionnaire_responses_user_id_completed_at", "user_id", desc("completed_at")),
    )
