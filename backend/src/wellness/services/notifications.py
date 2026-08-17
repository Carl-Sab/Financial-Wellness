"""Email delivery for check-in overspending risk notifications.

Every attempt is recorded in notification_outbox first (see models/
notifications.py) so there's an audit trail regardless of whether SMTP is
configured or delivery succeeds — this function never raises, so a mail
failure can't take down the check-in request that triggered it.
"""

from __future__ import annotations

import asyncio
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Literal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.config import get_settings
from wellness.models import NotificationOutbox, User
from wellness.models.enums import OutboxStatus

logger = structlog.get_logger()

RiskLevel = Literal["low", "medium", "high"]

_SUBJECTS: dict[RiskLevel, str] = {
    "low": "You're on track",
    "medium": "Heads up: possible overspending",
    "high": "Warning: high overspending risk",
}

_BODIES: dict[RiskLevel, str] = {
    "low": "You're safe — your recent check-in shows your spending is within a healthy range.",
    "medium": (
        "Pay attention — your recent check-in suggests a moderate risk of "
        "overspending. Consider slowing down."
    ),
    "high": (
        "Pay attention — your recent check-in shows a high risk of "
        "overspending. You may want to reconsider that purchase."
    ),
}


def _send_smtp(to_email: str, subject: str, body: str) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_email or settings.smtp_username
    message["To"] = to_email
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


async def notify_checkin_risk(
    session: AsyncSession,
    user: User,
    checkin_id: int,
    risk_level: RiskLevel,
    arousal_score: float,
) -> NotificationOutbox:
    settings = get_settings()
    body = _BODIES[risk_level]
    outbox = NotificationOutbox(
        user_id=user.id,
        checkin_id=checkin_id,
        body=body,
        trigger_reason=f"checkin_prediction:{risk_level}",
        arousal_score=arousal_score,
    )
    session.add(outbox)
    await session.flush()

    if not settings.smtp_host:
        outbox.status = OutboxStatus.SUPPRESSED
        outbox.suppression_reason = "SMTP is not configured"
        await session.commit()
        return outbox

    try:
        # smtplib is blocking; run it off the event loop thread so a slow or
        # unreachable mail server can't stall the request handling it.
        await asyncio.to_thread(_send_smtp, user.email, _SUBJECTS[risk_level], body)
    except Exception as exc:  # any SMTP failure must not fail the check-in
        logger.warning(
            "checkin_notification_send_failed", user_id=str(user.id), error=str(exc)
        )
        outbox.status = OutboxStatus.FAILED
        outbox.suppression_reason = str(exc)[:500]
    else:
        outbox.status = OutboxStatus.SENT
        outbox.sent_at = datetime.now(UTC)

    await session.commit()
    return outbox
