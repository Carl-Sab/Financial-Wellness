"""add user_goals, bank_accounts, bank_ledger; checkins.checkin_type

Adds three new tables in the spending domain (user_goals, bank_accounts,
bank_ledger) and one column on checkins. None of this is imported by, or
imports from, the arousal-scoring domain (checkins.py/baseline.py/arousal.py)
— see the boundary comment at the top of wellness/models/transactions.py.

Neither account balances nor goal progress are stored: both are always
derived at read time (balance = SUM over bank_ledger; goal progress = SUM
over transactions in the goal's period). No cached-total columns exist here
and none should be added later.

Constraint/index names are wrapped in sa.schema.conv() so they are used
exactly as given, matching what wellness.models' naming convention would
generate — see the note in 0001 for why this matters with Alembic.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import conv

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_LEDGER_DIRECTION_VALUES = ("credit", "debit")


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column(
        "checkins",
        sa.Column(
            "checkin_type",
            sa.Text(),
            server_default="pre_transaction",
            nullable=False,
        ),
    )

    ledger_direction = postgresql.ENUM(*_LEDGER_DIRECTION_VALUES, name="ledger_direction")
    ledger_direction.create(bind, checkfirst=True)

    op.create_table(
        "user_goals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("goal_type", sa.Text(), nullable=False),
        sa.Column("category_code", sa.Text(), nullable=True),
        sa.Column("target_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("period", sa.Text(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "target_amount > 0", name=conv("ck_user_goals_target_amount_positive")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=conv("fk_user_goals_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["category_code"],
            ["categories.code"],
            name=conv("fk_user_goals_category_code_categories"),
        ),
        sa.PrimaryKeyConstraint("id", name=conv("pk_user_goals")),
    )
    op.create_index(
        "ix_user_goals_user_id_active",
        "user_goals",
        ["user_id"],
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "bank_accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_number", sa.Text(), nullable=False),
        sa.Column("currency", sa.Text(), server_default="LBP", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=conv("fk_bank_accounts_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("account_number", name=conv("uq_bank_accounts_account_number")),
        sa.PrimaryKeyConstraint("id", name=conv("pk_bank_accounts")),
    )

    op.create_table(
        "bank_ledger",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "direction",
            postgresql.ENUM(*_LEDGER_DIRECTION_VALUES, name="ledger_direction", create_type=False),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # No ON DELETE action: a transaction must not be deletable out from
        # under a ledger entry.
        sa.Column("transaction_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("amount > 0", name=conv("ck_bank_ledger_amount_positive")),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["bank_accounts.id"],
            name=conv("fk_bank_ledger_account_id_bank_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name=conv("fk_bank_ledger_transaction_id_transactions"),
        ),
        sa.PrimaryKeyConstraint("id", name=conv("pk_bank_ledger")),
    )
    op.create_index(
        "ix_bank_ledger_account_id_occurred_at",
        "bank_ledger",
        ["account_id", sa.desc("occurred_at")],
    )


def downgrade() -> None:
    op.drop_table("bank_ledger")
    op.drop_table("bank_accounts")
    op.drop_table("user_goals")

    bind = op.get_bind()
    postgresql.ENUM(*_LEDGER_DIRECTION_VALUES, name="ledger_direction").drop(bind, checkfirst=True)

    op.drop_column("checkins", "checkin_type")
