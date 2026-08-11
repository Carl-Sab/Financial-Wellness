"""Refresh tokens and login rate limiting — the storage side of JWT auth.

Access tokens are short-lived JWTs: verified statelessly (a signature check
against SECRET_KEY, see security.py), never stored anywhere. Refresh tokens
are the opposite — long-lived and opaque, and only useful *because* they're
stored: this table is what makes revocation possible at all, which a bare
JWT can never support (there's nothing to delete; it's valid until it
expires, full stop).

Only a SHA-256 hash of the refresh token is stored, not the raw value —
same principle as password_hash on User, but a different hash for a
different reason: password hashing is deliberately slow (PBKDF2, many
iterations) to resist brute force against a human-chosen secret, but a
refresh token is already 32 bytes of CSPRNG output, so brute-forcing the
token itself is already infeasible. What a fast, deterministic hash buys
here is an indexed equality lookup on every refresh request — a slow salted
hash would mean re-hashing against every stored token to find a match, once
per request, which doesn't scale.

family_id links every token descended from one login through rotation.
Redeeming a refresh token marks it used_at and issues a new one sharing the
same family_id. If a token that already has used_at set is presented again,
that's not a race condition — it's proof the token was intercepted, so the
whole family gets revoked_at set and the legitimate holder is forced back
through login. See the /auth/refresh handler in api/v1/auth.py for that
logic; this module is just the tables.

No import from the spending domain (transactions/financial/banking/goals)
or the arousal-scoring domain (checkins/baseline/arousal) — both tables
here only ever reference users.id (refresh_tokens) or a plain email string
(login_failures), never anything from either domain.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from wellness.models.base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # SHA-256 hex digest of the opaque token actually sent to the client.
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # Shared by every token in one rotation chain — see the module docstring.
    family_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Set the moment this token is redeemed for a new one via rotation.
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set on logout, or across the whole family when reuse is detected.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        # Unique, not just indexed: this is also the lookup path for every
        # refresh request, and two rows hashing to the same value would be
        # a serious bug worth the database catching immediately.
        Index("ix_refresh_tokens_token_hash", "token_hash", unique=True),
    )


class LoginFailure(Base):
    """Backs the login rate limit (5 failures per email per 15 minutes)
    with a plain table instead of Redis — see the /auth/login handler.
    Only failed attempts are ever inserted; a successful login writes
    nothing here.

    Keyed by email, not user_id: rate limiting has to cover guesses against
    emails that don't belong to any account too, or a guessing attacker
    could tell real accounts apart by which emails *don't* get rate-limited.
    """

    __tablename__ = "login_failures"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Normalized (lowercased, trimmed) before storage — see api/v1/auth.py.
    email: Mapped[str] = mapped_column(Text, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_login_failures_email_attempted_at", "email", "attempted_at"),)
