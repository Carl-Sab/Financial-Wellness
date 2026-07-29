import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from wellness.models.base import Base, new_uuid
from wellness.models.enums import ConsentFeature


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # IANA tz name (e.g. "America/Denver"), used for display and for future quiet-hours logic.
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class UserConsent(Base):
    """Append-only per-feature consent log.

    Rows are never updated. A grant event sets granted_at and leaves revoked_at
    null; a revoke event sets revoked_at and leaves granted_at null. The current
    consent state for a (user_id, feature) pair is whichever row has the highest
    id (i.e. the most recently inserted). Biometric collection and notifications
    are tracked as separate features so one can be revoked without the other.
    """

    __tablename__ = "user_consent"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    feature: Mapped[ConsentFeature] = mapped_column(
        SAEnum(ConsentFeature, name="consent_feature", native_enum=True), nullable=False
    )
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_user_consent_user_feature_id", "user_id", "feature", "id"),
        CheckConstraint(
            "(granted_at IS NOT NULL) <> (revoked_at IS NOT NULL)",
            name="exactly_one_of_granted_or_revoked",
        ),
    )


class UserProfile(Base):
    """Slowly-changing demographic attributes, updated in place (not versioned)."""

    __tablename__ = "user_profile"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    age: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(160), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
