"""drop legacy arousal_state

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import conv

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

_AROUSAL_LABELS = ("calm", "elevated", "high", "unknown")


def upgrade() -> None:
    op.drop_table("arousal_state")
    postgresql.ENUM(*_AROUSAL_LABELS, name="arousal_label").drop(
        op.get_bind(), checkfirst=True
    )


def downgrade() -> None:
    arousal_label = postgresql.ENUM(*_AROUSAL_LABELS, name="arousal_label")
    arousal_label.create(op.get_bind(), checkfirst=True)
    arousal_label_column = postgresql.ENUM(
        *_AROUSAL_LABELS, name="arousal_label", create_type=False
    )

    op.create_table(
        "arousal_state",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("checkin_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("z_heart_rate", sa.REAL(), nullable=True),
        sa.Column("z_hrv", sa.REAL(), nullable=True),
        sa.Column("z_eda", sa.REAL(), nullable=True),
        sa.Column("z_spo2", sa.REAL(), nullable=True),
        sa.Column("z_skin_temp", sa.REAL(), nullable=True),
        sa.Column("score", sa.REAL(), nullable=True),
        sa.Column(
            "label", arousal_label_column, nullable=False, server_default="unknown"
        ),
        sa.Column("confidence", sa.REAL(), nullable=True),
        sa.Column("metrics_used", sa.SmallInteger(), nullable=False),
        sa.Column(
            "window_sample_count", sa.SmallInteger(), nullable=False, server_default="0"
        ),
        sa.Column(
            "reading_source", sa.Text(), nullable=False, server_default="checkins"
        ),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "score BETWEEN 0 AND 1", name=conv("ck_arousal_state_score_range")
        ),
        sa.CheckConstraint(
            "confidence BETWEEN 0 AND 1",
            name=conv("ck_arousal_state_confidence_range"),
        ),
        sa.ForeignKeyConstraint(
            ["checkin_id"],
            ["checkins.id"],
            name=conv("fk_arousal_state_checkin_id_checkins"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=conv("fk_arousal_state_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=conv("pk_arousal_state")),
        sa.UniqueConstraint(
            "checkin_id", name=conv("uq_arousal_state_checkin_id")
        ),
    )
    op.create_index(
        "ix_arousal_state_user_id_computed_at",
        "arousal_state",
        ["user_id", sa.desc("computed_at")],
    )
