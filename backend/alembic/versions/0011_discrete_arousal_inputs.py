"""add discrete manual and detailed arousal inputs

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.schema import conv

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

_DISCRETE_VALUES = "(-2, -1, 0, 1, 2)"


def upgrade() -> None:
    op.add_column("checkins", sa.Column("arousal_input_mode", sa.Text(), nullable=True))
    for column_name in (
        "arousal_z",
        "z_hr",
        "perceived_hrv",
        "perceived_eda",
        "perceived_respiration",
        "perceived_skin_temperature",
    ):
        op.add_column("checkins", sa.Column(column_name, sa.REAL(), nullable=True))

    op.drop_constraint(
        conv("ck_checkins_at_least_one_reading"), "checkins", type_="check"
    )
    op.create_check_constraint(
        conv("ck_checkins_arousal_input_mode_values"),
        "checkins",
        "arousal_input_mode IS NULL OR arousal_input_mode IN ('manual', 'detailed')",
    )
    discrete_checks = " AND ".join(
        f"({column} IS NULL OR {column} IN {_DISCRETE_VALUES})"
        for column in (
            "arousal_z",
            "z_hr",
            "perceived_hrv",
            "perceived_eda",
            "perceived_respiration",
            "perceived_skin_temperature",
        )
    )
    op.create_check_constraint(
        conv("ck_checkins_arousal_values_discrete"), "checkins", discrete_checks
    )
    op.create_check_constraint(
        conv("ck_checkins_arousal_input_contract"),
        "checkins",
        "(arousal_input_mode IS NULL "
        "AND (heart_rate IS NOT NULL OR hrv_ms IS NOT NULL OR eda_microsiemens IS NOT NULL "
        "OR spo2_percent IS NOT NULL OR skin_temp_c IS NOT NULL OR eeg_value IS NOT NULL) "
        "AND arousal_z IS NULL AND z_hr IS NULL AND perceived_hrv IS NULL "
        "AND perceived_eda IS NULL AND perceived_respiration IS NULL "
        "AND perceived_skin_temperature IS NULL) "
        "OR (arousal_input_mode = 'manual' AND arousal_z IS NOT NULL "
        "AND z_hr IS NULL AND perceived_hrv IS NULL AND perceived_eda IS NULL "
        "AND perceived_respiration IS NULL AND perceived_skin_temperature IS NULL "
        "AND heart_rate IS NULL AND hrv_ms IS NULL AND eda_microsiemens IS NULL "
        "AND spo2_percent IS NULL AND skin_temp_c IS NULL AND eeg_value IS NULL) "
        "OR (arousal_input_mode = 'detailed' AND arousal_z IS NULL "
        "AND z_hr IS NOT NULL AND perceived_hrv IS NOT NULL AND perceived_eda IS NOT NULL "
        "AND perceived_respiration IS NOT NULL AND perceived_skin_temperature IS NOT NULL "
        "AND heart_rate IS NULL AND hrv_ms IS NULL AND eda_microsiemens IS NULL "
        "AND spo2_percent IS NULL AND skin_temp_c IS NULL AND eeg_value IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        conv("ck_checkins_arousal_input_contract"), "checkins", type_="check"
    )
    op.drop_constraint(
        conv("ck_checkins_arousal_values_discrete"), "checkins", type_="check"
    )
    op.drop_constraint(
        conv("ck_checkins_arousal_input_mode_values"), "checkins", type_="check"
    )
    op.create_check_constraint(
        conv("ck_checkins_at_least_one_reading"),
        "checkins",
        "heart_rate IS NOT NULL OR hrv_ms IS NOT NULL OR eda_microsiemens IS NOT NULL "
        "OR spo2_percent IS NOT NULL OR skin_temp_c IS NOT NULL OR eeg_value IS NOT NULL",
    )
    for column_name in (
        "perceived_skin_temperature",
        "perceived_respiration",
        "perceived_eda",
        "perceived_hrv",
        "z_hr",
        "arousal_z",
        "arousal_input_mode",
    ):
        op.drop_column("checkins", column_name)
