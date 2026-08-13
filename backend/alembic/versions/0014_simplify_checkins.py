"""simplify checkins to subjective arousal inputs

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.schema import conv

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for constraint_name in (
        "ck_checkins_arousal_input_contract",
        "ck_checkins_arousal_values_discrete",
        "ck_checkins_heart_rate_range",
        "ck_checkins_hrv_ms_range",
        "ck_checkins_eda_microsiemens_range",
        "ck_checkins_spo2_percent_range",
        "ck_checkins_skin_temp_c_range",
    ):
        op.drop_constraint(conv(constraint_name), "checkins", type_="check")

    op.alter_column("checkins", "z_hr", new_column_name="perceived_heart_rate")
    op.alter_column(
        "checkins", "perceived_hrv", new_column_name="perceived_heartbeat_steadiness"
    )
    op.alter_column("checkins", "perceived_eda", new_column_name="perceived_sweating")
    op.alter_column(
        "checkins",
        "perceived_skin_temperature",
        new_column_name="perceived_temperature_difference",
    )

    for column_name in (
        "heart_rate",
        "hrv_ms",
        "eda_microsiemens",
        "spo2_percent",
        "skin_temp_c",
        "eeg_value",
        "checkin_type",
    ):
        op.drop_column("checkins", column_name)

    op.create_check_constraint(
        conv("ck_checkins_arousal_values_discrete"),
        "checkins",
        "(arousal_z IS NULL OR arousal_z IN (-2, -1, 0, 1, 2)) "
        "AND (perceived_heart_rate IS NULL "
        "OR perceived_heart_rate IN (-2, -1, 0, 1, 2)) "
        "AND (perceived_heartbeat_steadiness IS NULL "
        "OR perceived_heartbeat_steadiness IN (-2, -1, 0, 1, 2)) "
        "AND (perceived_sweating IS NULL OR perceived_sweating IN (-2, -1, 0, 1, 2)) "
        "AND (perceived_respiration IS NULL "
        "OR perceived_respiration IN (-2, -1, 0, 1, 2)) "
        "AND (perceived_temperature_difference IS NULL "
        "OR perceived_temperature_difference IN (-2, -1, 0, 1, 2))",
    )
    op.create_check_constraint(
        conv("ck_checkins_arousal_input_contract"),
        "checkins",
        "(arousal_input_mode IS NULL AND arousal_z IS NULL "
        "AND perceived_heart_rate IS NULL AND perceived_heartbeat_steadiness IS NULL "
        "AND perceived_sweating IS NULL AND perceived_respiration IS NULL "
        "AND perceived_temperature_difference IS NULL) "
        "OR (arousal_input_mode = 'manual' AND arousal_z IS NOT NULL "
        "AND perceived_heart_rate IS NULL AND perceived_heartbeat_steadiness IS NULL "
        "AND perceived_sweating IS NULL AND perceived_respiration IS NULL "
        "AND perceived_temperature_difference IS NULL) "
        "OR (arousal_input_mode = 'detailed' AND arousal_z IS NULL "
        "AND perceived_heart_rate IS NOT NULL "
        "AND perceived_heartbeat_steadiness IS NOT NULL "
        "AND perceived_sweating IS NOT NULL AND perceived_respiration IS NOT NULL "
        "AND perceived_temperature_difference IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        conv("ck_checkins_arousal_input_contract"), "checkins", type_="check"
    )
    op.drop_constraint(
        conv("ck_checkins_arousal_values_discrete"), "checkins", type_="check"
    )

    op.add_column(
        "checkins",
        sa.Column("checkin_type", sa.Text(), nullable=False, server_default="pre_transaction"),
    )
    for column_name in (
        "heart_rate",
        "hrv_ms",
        "eda_microsiemens",
        "spo2_percent",
        "skin_temp_c",
        "eeg_value",
    ):
        op.add_column("checkins", sa.Column(column_name, sa.REAL(), nullable=True))

    op.alter_column(
        "checkins",
        "perceived_temperature_difference",
        new_column_name="perceived_skin_temperature",
    )
    op.alter_column("checkins", "perceived_sweating", new_column_name="perceived_eda")
    op.alter_column(
        "checkins", "perceived_heartbeat_steadiness", new_column_name="perceived_hrv"
    )
    op.alter_column("checkins", "perceived_heart_rate", new_column_name="z_hr")

    for constraint_name, expression in (
        ("ck_checkins_heart_rate_range", "heart_rate BETWEEN 30 AND 220"),
        ("ck_checkins_hrv_ms_range", "hrv_ms BETWEEN 1 AND 300"),
        ("ck_checkins_eda_microsiemens_range", "eda_microsiemens BETWEEN 0 AND 100"),
        ("ck_checkins_spo2_percent_range", "spo2_percent BETWEEN 70 AND 100"),
        ("ck_checkins_skin_temp_c_range", "skin_temp_c BETWEEN 30 AND 43"),
    ):
        op.create_check_constraint(conv(constraint_name), "checkins", expression)

    op.create_check_constraint(
        conv("ck_checkins_arousal_values_discrete"),
        "checkins",
        "(arousal_z IS NULL OR arousal_z IN (-2, -1, 0, 1, 2)) "
        "AND (z_hr IS NULL OR z_hr IN (-2, -1, 0, 1, 2)) "
        "AND (perceived_hrv IS NULL OR perceived_hrv IN (-2, -1, 0, 1, 2)) "
        "AND (perceived_eda IS NULL OR perceived_eda IN (-2, -1, 0, 1, 2)) "
        "AND (perceived_respiration IS NULL "
        "OR perceived_respiration IN (-2, -1, 0, 1, 2)) "
        "AND (perceived_skin_temperature IS NULL "
        "OR perceived_skin_temperature IN (-2, -1, 0, 1, 2))",
    )
    op.create_check_constraint(
        conv("ck_checkins_arousal_input_contract"),
        "checkins",
        "(arousal_input_mode IS NULL AND arousal_z IS NULL AND z_hr IS NULL "
        "AND perceived_hrv IS NULL "
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
