"""remove wearable samples and computed user baselines

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import conv

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("biometric_samples")
    op.drop_table("user_baseline")


def downgrade() -> None:
    op.create_table(
        "user_baseline",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("mean_value", sa.REAL(), nullable=False),
        sa.Column("sd_value", sa.REAL(), nullable=True),
        sa.Column("sample_n", sa.Integer(), nullable=False),
        sa.Column("min_value", sa.REAL(), nullable=True),
        sa.Column("max_value", sa.REAL(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="checkins"),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=conv("fk_user_baseline_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "metric", name=conv("pk_user_baseline")
        ),
    )
    op.create_table(
        "biometric_samples",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heart_rate", sa.REAL(), nullable=True),
        sa.Column("hrv_ms", sa.REAL(), nullable=True),
        sa.Column("spo2_percent", sa.REAL(), nullable=True),
        sa.Column("data_source", sa.Text(), nullable=False, server_default="wearable"),
        sa.CheckConstraint(
            "heart_rate BETWEEN 30 AND 220",
            name=conv("ck_biometric_samples_heart_rate_range"),
        ),
        sa.CheckConstraint(
            "hrv_ms BETWEEN 1 AND 300",
            name=conv("ck_biometric_samples_hrv_ms_range"),
        ),
        sa.CheckConstraint(
            "spo2_percent BETWEEN 70 AND 100",
            name=conv("ck_biometric_samples_spo2_percent_range"),
        ),
        sa.CheckConstraint(
            "heart_rate IS NOT NULL OR hrv_ms IS NOT NULL OR spo2_percent IS NOT NULL",
            name=conv("ck_biometric_samples_at_least_one_reading"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=conv("fk_biometric_samples_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=conv("pk_biometric_samples")),
        sa.UniqueConstraint(
            "user_id",
            "ts",
            "data_source",
            name=conv("uq_biometric_samples_user_id_ts_data_source"),
        ),
    )
    op.create_index(
        "ix_biometric_samples_user_id_ts",
        "biometric_samples",
        ["user_id", sa.desc("ts")],
    )
