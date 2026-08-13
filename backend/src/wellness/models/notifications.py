"""Notification outbox and delivery feedback.

The notification outbox references checkin_id and carries a snapshotted
arousal_score as plain columns, so this module does not need to import the
check-in model.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    REAL,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Text,
    desc,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from wellness.models.base import Base
from wellness.models.enums import FeedbackEvent, OutboxStatus

# values_callable: see the note in categories.py — without it SQLAlchemy
# binds the member name ("PENDING") instead of its value ("pending").
outbox_status_enum = SAEnum(
    OutboxStatus,
    name="outbox_status",
    native_enum=True,
    values_callable=lambda cls: [e.value for e in cls],
)
feedback_event_enum = SAEnum(
    FeedbackEvent,
    name="feedback_event",
    native_enum=True,
    values_callable=lambda cls: [e.value for e in cls],
)


class NotificationOutbox(Base):
    """Intended notification, written here before delivery is attempted.

    arousal_score is a snapshot value rather than a foreign key, so the
    outbox row remains meaningful if prediction data changes later.
    """

    __tablename__ = "notification_outbox"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    checkin_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("checkins.id"), nullable=True
    )
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_reason: Mapped[str] = mapped_column(Text, nullable=False)
    arousal_score: Mapped[float | None] = mapped_column(REAL, nullable=True)
    status: Mapped[OutboxStatus] = mapped_column(
        outbox_status_enum,
        nullable=False,
        default=OutboxStatus.PENDING,
        server_default=OutboxStatus.PENDING.value,
    )
    suppression_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    used_fallback: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_notification_outbox_user_id_created_at", "user_id", desc("created_at")),
    )


class NotificationFeedback(Base):
    __tablename__ = "notification_feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    outbox_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("notification_outbox.id", ondelete="CASCADE"), nullable=False
    )
    event: Mapped[FeedbackEvent] = mapped_column(feedback_event_enum, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
