"""reconcile normalization snapshots in existing development databases

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-13

Revision 0019 was replaced while a local Compose database was already stamped
at that revision. Fresh databases already have the table, so this compatibility
migration is intentionally conditional.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import conv

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "user_normalization_snapshots" in sa.inspect(bind).get_table_names():
        return

    op.create_table(
        "user_normalization_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("heart_rate_mean", sa.REAL(), nullable=False),
        sa.Column("heart_rate_std", sa.REAL(), nullable=False),
        sa.Column("hrv_sdnn_mean", sa.REAL(), nullable=False),
        sa.Column("hrv_sdnn_std", sa.REAL(), nullable=False),
        sa.Column("skin_conductance_mean", sa.REAL(), nullable=False),
        sa.Column("skin_conductance_std", sa.REAL(), nullable=False),
        sa.Column("respiration_rate_mean", sa.REAL(), nullable=False),
        sa.Column("respiration_rate_std", sa.REAL(), nullable=False),
        sa.Column("skin_temperature_mean", sa.REAL(), nullable=False),
        sa.Column("skin_temperature_std", sa.REAL(), nullable=False),
        sa.Column("impulse_tendency_mean", sa.REAL(), nullable=False),
        sa.Column("impulse_tendency_std", sa.REAL(), nullable=False),
        sa.Column("self_control_mean", sa.REAL(), nullable=False),
        sa.Column("self_control_std", sa.REAL(), nullable=False),
        sa.Column("hedonic_mean", sa.REAL(), nullable=False),
        sa.Column("hedonic_std", sa.REAL(), nullable=False),
        sa.Column("utilitarian_mean", sa.REAL(), nullable=False),
        sa.Column("utilitarian_std", sa.REAL(), nullable=False),
        sa.Column("normative_evaluation_mean", sa.REAL(), nullable=False),
        sa.Column("normative_evaluation_std", sa.REAL(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "heart_rate_std >= 0 AND hrv_sdnn_std >= 0 "
            "AND skin_conductance_std >= 0 AND respiration_rate_std >= 0 "
            "AND skin_temperature_std >= 0 AND impulse_tendency_std >= 0 "
            "AND self_control_std >= 0 AND hedonic_std >= 0 "
            "AND utilitarian_std >= 0 AND normative_evaluation_std >= 0",
            name=conv(
                "ck_user_normalization_snapshots_standard_deviations_non_negative"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=conv("fk_user_normalization_snapshots_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id", name=conv("pk_user_normalization_snapshots")
        ),
    )
    op.create_index(
        "ix_user_normalization_snapshots_user_id_recorded_at",
        "user_normalization_snapshots",
        ["user_id", sa.desc("recorded_at"), sa.desc("id")],
    )
    op.execute(
        """
        INSERT INTO user_normalization_snapshots (
            user_id,
            heart_rate_mean, heart_rate_std,
            hrv_sdnn_mean, hrv_sdnn_std,
            skin_conductance_mean, skin_conductance_std,
            respiration_rate_mean, respiration_rate_std,
            skin_temperature_mean, skin_temperature_std,
            impulse_tendency_mean, impulse_tendency_std,
            self_control_mean, self_control_std,
            hedonic_mean, hedonic_std,
            utilitarian_mean, utilitarian_std,
            normative_evaluation_mean, normative_evaluation_std,
            recorded_at
        )
        SELECT
            id,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            2.661558, 0.831699,
            3.037315, 0.660859,
            4.636136363636, 1.022405590475,
            4.276041666667, 1.084810087389,
            2.985884, 0.660152,
            created_at
        FROM users
        """
    )


def downgrade() -> None:
    # 0019 owns this table in the canonical migration history. The upgrade
    # only restores that expected state for a database affected by the local
    # revision replacement, so stepping back to 0019 keeps the table.
    pass
