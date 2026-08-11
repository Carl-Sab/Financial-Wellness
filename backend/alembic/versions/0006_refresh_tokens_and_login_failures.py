"""add refresh_tokens and login_failures for JWT auth

refresh_tokens: the revocable half of the JWT pair — access tokens are
short-lived JWTs, verified statelessly and never stored; refresh tokens are
long-lived, opaque, and stored (as a SHA-256 hash, never the raw token) so
they can actually be revoked. family_id links every token produced by
rotating the same original login into one chain, so reuse of an
already-used token can revoke that whole chain, not just the one token.
See wellness/models/auth.py and the login/refresh/logout handlers in
wellness/api/v1/auth.py.

login_failures: backs the login rate limit (5 failures per email per 15
minutes) with a plain table instead of Redis. Only failed attempts are
recorded; keyed by email rather than user_id so guesses against emails
that don't exist are rate-limited too, not just real accounts.

Constraint/index names are wrapped in sa.schema.conv() so they are used
exactly as given, matching what wellness.models' naming convention would
generate — see the note in 0004.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import conv

# revision identifiers, used by Alembic.
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=conv("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=conv("pk_refresh_tokens")),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index(
        "ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True
    )

    op.create_table(
        "login_failures",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=conv("pk_login_failures")),
    )
    op.create_index(
        "ix_login_failures_email_attempted_at", "login_failures", ["email", "attempted_at"]
    )


def downgrade() -> None:
    op.drop_table("login_failures")
    op.drop_table("refresh_tokens")
