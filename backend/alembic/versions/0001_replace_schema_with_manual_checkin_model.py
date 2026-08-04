"""replace schema with manual check-in model

Replaces the old wearable-stream / TimescaleDB schema with the v3 schema
(schema.sql at the repo root): manually entered check-ins, per-user
baselines computed from check-in history, and z-score-derived arousal
state. The old tables are dropped, not migrated in place — the data model
changed too much for an in-place ALTER to make sense, and no production
data exists yet to preserve.

All constraint/index names below are wrapped in sa.schema.conv() so they are
used exactly as given. Without it, Alembic copies target_metadata's naming
convention onto the ad-hoc MetaData this migration builds, and conventions
that reference %(constraint_name)s (e.g. "ck") silently re-wrap an
already-final name (turning "ck_checkins_x" into "ck_checkins_ck_checkins_x").
The names chosen here match exactly what wellness.models' naming convention
would generate from the ORM models, so a future `alembic revision
--autogenerate` sees no spurious diff.

Revision ID: 0001
Revises:
Create Date: 2026-08-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import conv

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Old (v2) tables. Some names are reused by the v3 schema with entirely
# different columns (e.g. "users", "arousal_state", "financial_profile");
# CASCADE drops those old definitions along with any dependent old
# constraints/indexes before the v3 tables are created below. The rest
# (biometric_samples, user_profile, user_consent) have no v3 equivalent and
# are simply removed.
_OLD_TABLES = (
    "notification_feedback",
    "notification_outbox",
    "financial_profile",
    "arousal_state",
    "user_baseline",
    "biometric_samples",
    "user_profile",
    "user_consent",
    "users",
)

# Old enum types. "arousal_label" is recreated below with an added
# 'unknown' value, so it must be dropped rather than altered in place.
# "notification_status" / "notification_feedback_event" are superseded by
# the differently named "outbox_status" / "feedback_event".
_OLD_ENUM_TYPES = (
    "consent_feature",
    "biometric_quality_flag",
    "arousal_label",
    "notification_status",
    "notification_feedback_event",
)

_LEVEL_3_VALUES = ("low", "mid", "high")
_VALENCE_LEVEL_VALUES = ("very_unpleasant", "unpleasant", "neutral", "pleasant", "very_pleasant")
_AROUSAL_LABEL_VALUES = ("calm", "elevated", "high", "unknown")
_OUTBOX_STATUS_VALUES = ("pending", "sent", "failed", "suppressed")
_FEEDBACK_EVENT_VALUES = ("delivered", "opened", "dismissed", "marked_helpful", "marked_not_now")


def upgrade() -> None:
    bind = op.get_bind()

    # --- remove the old (v2) schema ----------------------------------
    for table in _OLD_TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    for enum_type in _OLD_ENUM_TYPES:
        op.execute(f"DROP TYPE IF EXISTS {enum_type}")

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # --- v3 enum types -------------------------------------------------
    level_3 = postgresql.ENUM(*_LEVEL_3_VALUES, name="level_3")
    valence_level = postgresql.ENUM(*_VALENCE_LEVEL_VALUES, name="valence_level")
    arousal_label = postgresql.ENUM(*_AROUSAL_LABEL_VALUES, name="arousal_label")
    outbox_status = postgresql.ENUM(*_OUTBOX_STATUS_VALUES, name="outbox_status")
    feedback_event = postgresql.ENUM(*_FEEDBACK_EVENT_VALUES, name="feedback_event")
    for enum in (level_3, valence_level, arousal_label, outbox_status, feedback_event):
        enum.create(bind, checkfirst=True)

    # --- tables, in dependency order -----------------------------------
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("timezone", sa.Text(), server_default="Asia/Beirut", nullable=False),
        sa.Column("currency", sa.Text(), server_default="LBP", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=conv("pk_users")),
        sa.UniqueConstraint("email", name=conv("uq_users_email")),
    )

    level_3_col = postgresql.ENUM(*_LEVEL_3_VALUES, name="level_3", create_type=False)
    valence_level_col = postgresql.ENUM(
        *_VALENCE_LEVEL_VALUES, name="valence_level", create_type=False
    )

    op.create_table(
        "categories",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("identity_level", level_3_col, nullable=False),
        sa.Column("price_level", level_3_col, nullable=False),
        sa.Column("advertising_level", level_3_col, nullable=False),
        sa.Column("distribution_level", level_3_col, nullable=False),
        sa.Column("stimuli_score", sa.REAL(), nullable=True),
        sa.PrimaryKeyConstraint("code", name=conv("pk_categories")),
    )

    op.create_table(
        "checkins",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_code", sa.Text(), nullable=False),
        sa.Column("valence", valence_level_col, nullable=False),
        sa.Column("heart_rate", sa.REAL(), nullable=True),
        sa.Column("hrv_ms", sa.REAL(), nullable=True),
        sa.Column("eda_microsiemens", sa.REAL(), nullable=True),
        sa.Column("spo2_percent", sa.REAL(), nullable=True),
        sa.Column("skin_temp_c", sa.REAL(), nullable=True),
        sa.Column("eeg_value", sa.REAL(), nullable=True),
        sa.Column(
            "entered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "heart_rate BETWEEN 30 AND 220", name=conv("ck_checkins_heart_rate_range")
        ),
        sa.CheckConstraint("hrv_ms BETWEEN 1 AND 300", name=conv("ck_checkins_hrv_ms_range")),
        sa.CheckConstraint(
            "eda_microsiemens BETWEEN 0 AND 100",
            name=conv("ck_checkins_eda_microsiemens_range"),
        ),
        sa.CheckConstraint(
            "spo2_percent BETWEEN 70 AND 100", name=conv("ck_checkins_spo2_percent_range")
        ),
        sa.CheckConstraint(
            "skin_temp_c BETWEEN 30 AND 43", name=conv("ck_checkins_skin_temp_c_range")
        ),
        sa.CheckConstraint(
            "heart_rate IS NOT NULL OR hrv_ms IS NOT NULL OR eda_microsiemens IS NOT NULL "
            "OR spo2_percent IS NOT NULL OR skin_temp_c IS NOT NULL OR eeg_value IS NOT NULL",
            name=conv("ck_checkins_at_least_one_reading"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=conv("fk_checkins_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_code"],
            ["categories.code"],
            name=conv("fk_checkins_category_code_categories"),
        ),
        sa.PrimaryKeyConstraint("id", name=conv("pk_checkins")),
    )

    op.create_table(
        "user_baseline",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("mean_value", sa.REAL(), nullable=False),
        sa.Column("sd_value", sa.REAL(), nullable=True),
        sa.Column("sample_n", sa.Integer(), nullable=False),
        sa.Column("min_value", sa.REAL(), nullable=True),
        sa.Column("max_value", sa.REAL(), nullable=True),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=conv("fk_user_baseline_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "metric", name=conv("pk_user_baseline")),
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
            "label",
            postgresql.ENUM(*_AROUSAL_LABEL_VALUES, name="arousal_label", create_type=False),
            server_default="unknown",
            nullable=False,
        ),
        sa.Column("confidence", sa.REAL(), nullable=True),
        sa.Column("metrics_used", sa.SmallInteger(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("score BETWEEN 0 AND 1", name=conv("ck_arousal_state_score_range")),
        sa.CheckConstraint(
            "confidence BETWEEN 0 AND 1", name=conv("ck_arousal_state_confidence_range")
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
        sa.UniqueConstraint("checkin_id", name=conv("uq_arousal_state_checkin_id")),
    )

    op.create_table(
        "questionnaire_responses",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("impulse_tendency_score", sa.REAL(), nullable=True),
        sa.Column("self_control_score", sa.REAL(), nullable=True),
        sa.Column("hedonic_score", sa.REAL(), nullable=True),
        sa.Column("utilitarian_score", sa.REAL(), nullable=True),
        sa.Column("raw_responses", postgresql.JSONB(), nullable=False),
        sa.Column("instrument_version", sa.Text(), server_default="v1", nullable=False),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "impulse_tendency_score BETWEEN 1 AND 5",
            name=conv("ck_questionnaire_responses_impulse_tendency_score_range"),
        ),
        sa.CheckConstraint(
            "self_control_score BETWEEN 1 AND 5",
            name=conv("ck_questionnaire_responses_self_control_score_range"),
        ),
        sa.CheckConstraint(
            "hedonic_score BETWEEN 1 AND 7",
            name=conv("ck_questionnaire_responses_hedonic_score_range"),
        ),
        sa.CheckConstraint(
            "utilitarian_score BETWEEN 1 AND 7",
            name=conv("ck_questionnaire_responses_utilitarian_score_range"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=conv("fk_questionnaire_responses_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=conv("pk_questionnaire_responses")),
    )

    op.create_table(
        "user_settings",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quiet_hours_start", sa.Time(), server_default="22:00", nullable=False),
        sa.Column("quiet_hours_end", sa.Time(), server_default="08:00", nullable=False),
        sa.Column("max_notifs_per_day", sa.SmallInteger(), server_default="3", nullable=False),
        sa.Column(
            "notifications_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("notifications_muted_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=conv("fk_user_settings_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=conv("pk_user_settings")),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checkin_id", sa.BigInteger(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.Text(), server_default="LBP", nullable=False),
        sa.Column("category_code", sa.Text(), nullable=False),
        sa.Column("merchant_name", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("was_planned", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("amount >= 0", name=conv("ck_transactions_amount_non_negative")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=conv("fk_transactions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["checkin_id"], ["checkins.id"], name=conv("fk_transactions_checkin_id_checkins")
        ),
        sa.ForeignKeyConstraint(
            ["category_code"],
            ["categories.code"],
            name=conv("fk_transactions_category_code_categories"),
        ),
        sa.PrimaryKeyConstraint("id", name=conv("pk_transactions")),
    )

    op.create_table(
        "financial_profile",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("monthly_income", sa.Numeric(14, 2), nullable=True),
        sa.Column("avg_monthly_spend", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.Text(), server_default="LBP", nullable=False),
        sa.Column(
            "valid_from", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=conv("fk_financial_profile_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=conv("pk_financial_profile")),
    )

    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checkin_id", sa.BigInteger(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("trigger_reason", sa.Text(), nullable=False),
        sa.Column("arousal_score", sa.REAL(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(*_OUTBOX_STATUS_VALUES, name="outbox_status", create_type=False),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("suppression_reason", sa.Text(), nullable=True),
        sa.Column("used_fallback", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=conv("fk_notification_outbox_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["checkin_id"],
            ["checkins.id"],
            name=conv("fk_notification_outbox_checkin_id_checkins"),
        ),
        sa.PrimaryKeyConstraint("id", name=conv("pk_notification_outbox")),
    )

    op.create_table(
        "notification_feedback",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("outbox_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "event",
            postgresql.ENUM(*_FEEDBACK_EVENT_VALUES, name="feedback_event", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["outbox_id"],
            ["notification_outbox.id"],
            name=conv("fk_notification_feedback_outbox_id_notification_outbox"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=conv("pk_notification_feedback")),
    )

    # --- indexes ---------------------------------------------------------
    op.create_index(
        "ix_checkins_user_id_entered_at", "checkins", ["user_id", sa.desc("entered_at")]
    )
    op.create_index(
        "ix_questionnaire_responses_user_id_completed_at",
        "questionnaire_responses",
        ["user_id", sa.desc("completed_at")],
    )
    op.create_index(
        "one_current_financial_profile",
        "financial_profile",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("valid_to IS NULL"),
    )
    op.create_index(
        "ix_arousal_state_user_id_computed_at",
        "arousal_state",
        ["user_id", sa.desc("computed_at")],
    )
    op.create_index(
        "ix_notification_outbox_user_id_created_at",
        "notification_outbox",
        ["user_id", sa.desc("created_at")],
    )
    op.create_index(
        "ix_transactions_user_id_occurred_at", "transactions", ["user_id", sa.desc("occurred_at")]
    )
    op.create_index(
        "ix_transactions_user_id_category_code_occurred_at",
        "transactions",
        ["user_id", "category_code", sa.desc("occurred_at")],
    )

    # --- seed data ---------------------------------------------------------
    op.execute(
        """
        INSERT INTO categories (code, label, identity_level, price_level,
                                advertising_level, distribution_level) VALUES
         ('groceries',   'Groceries',   'low',  'low',  'high', 'high'),
         ('clothing',    'Clothing',    'high', 'mid',  'high', 'mid'),
         ('restaurant',  'Restaurant',  'low',  'low',  'mid',  'high'),
         ('electronics', 'Electronics', 'mid',  'high', 'high', 'mid'),
         ('mall',        'Mall',        'high', 'mid',  'high', 'mid'),
         ('online',      'Online',      'mid',  'low',  'high', 'high'),
         ('other',       'Other',       'mid',  'mid',  'mid',  'mid')
        """
    )
    op.execute(
        """
        UPDATE categories SET stimuli_score = ROUND((
              (CASE identity_level     WHEN 'low' THEN 0 WHEN 'mid' THEN 0.5 ELSE 1 END)
            - (CASE price_level        WHEN 'low' THEN 0 WHEN 'mid' THEN 0.5 ELSE 1 END)
            - (CASE distribution_level WHEN 'low' THEN 0 WHEN 'mid' THEN 0.5 ELSE 1 END) * 0.5
            + (CASE advertising_level  WHEN 'low' THEN 0 WHEN 'mid' THEN 0.5 ELSE 1 END) * 0.5
            + 0.25)::numeric, 2)
        """
    )


def downgrade() -> None:
    op.drop_table("notification_feedback")
    op.drop_table("notification_outbox")
    op.drop_table("financial_profile")
    op.drop_table("transactions")
    op.drop_table("user_settings")
    op.drop_table("questionnaire_responses")
    op.drop_table("arousal_state")
    op.drop_table("user_baseline")
    op.drop_table("checkins")
    op.drop_table("categories")
    op.drop_table("users")

    bind = op.get_bind()
    for name, values in (
        ("feedback_event", _FEEDBACK_EVENT_VALUES),
        ("outbox_status", _OUTBOX_STATUS_VALUES),
        ("arousal_label", _AROUSAL_LABEL_VALUES),
        ("valence_level", _VALENCE_LEVEL_VALUES),
        ("level_3", _LEVEL_3_VALUES),
    ):
        postgresql.ENUM(*values, name=name).drop(bind, checkfirst=True)
