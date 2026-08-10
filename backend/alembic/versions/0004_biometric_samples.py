"""add biometric_samples

HealthKit (and other wearable) sample ingestion — arousal-scoring domain.
See wellness/models/biometric_samples.py: independent of checkins for now,
not yet fed into refresh_baseline()/score_checkin().

Constraint/index names are wrapped in sa.schema.conv() so they are used
exactly as given, matching what wellness.models' naming convention would
generate — see the note in 0001 for why this matters with Alembic.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import conv

# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "biometric_samples",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heart_rate", sa.REAL(), nullable=True),
        sa.Column("hrv_ms", sa.REAL(), nullable=True),
        sa.Column("spo2_percent", sa.REAL(), nullable=True),
        sa.Column(
            "data_source", sa.Text(), server_default="healthkit", nullable=False
        ),
        sa.Column(
            "ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "heart_rate BETWEEN 30 AND 220", name=conv("ck_biometric_samples_heart_rate_range")
        ),
        sa.CheckConstraint(
            "hrv_ms BETWEEN 1 AND 300", name=conv("ck_biometric_samples_hrv_ms_range")
        ),
        sa.CheckConstraint(
            "spo2_percent BETWEEN 70 AND 100", name=conv("ck_biometric_samples_spo2_percent_range")
        ),
        sa.CheckConstraint(
            "heart_rate IS NOT NULL OR hrv_ms IS NOT NULL OR spo2_percent IS NOT NULL",
            name=conv("ck_biometric_samples_at_least_one_reading"),
        ),
        sa.UniqueConstraint(
            "user_id",
            "ts",
            "data_source",
            name=conv("uq_biometric_samples_user_id_ts_data_source"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=conv("fk_biometric_samples_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=conv("pk_biometric_samples")),
    )
    op.create_index(
        "ix_biometric_samples_user_id_ts", "biometric_samples", ["user_id", sa.desc("ts")]
    )


def downgrade() -> None:
    op.drop_table("biometric_samples")
