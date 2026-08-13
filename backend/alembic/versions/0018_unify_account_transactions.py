"""unify account movements in transactions

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import conv

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

_DIRECTIONS = ("credit", "debit")


def upgrade() -> None:
    # Reuse the existing enum values under a name that matches their new owner.
    op.execute("ALTER TYPE ledger_direction RENAME TO transaction_direction")
    direction_type = postgresql.ENUM(
        *_DIRECTIONS, name="transaction_direction", create_type=False
    )

    op.add_column(
        "bank_accounts",
        sa.Column(
            "opening_balance",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column("transactions", sa.Column("account_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "transactions",
        sa.Column("direction", direction_type, nullable=False, server_default="debit"),
    )
    op.add_column("transactions", sa.Column("description", sa.Text(), nullable=True))
    op.alter_column(
        "transactions", "category_code", existing_type=sa.Text(), nullable=True
    )
    op.create_foreign_key(
        conv("fk_transactions_account_id_bank_accounts"),
        "transactions",
        "bank_accounts",
        ["account_id"],
        ["id"],
    )
    op.create_index(
        "ix_transactions_account_id_occurred_at",
        "transactions",
        ["account_id", sa.desc("occurred_at")],
    )

    # Older/smoke-test users may predate automatic account creation. Give each
    # of them a deterministic account before account_id becomes mandatory.
    op.execute(
        """
        INSERT INTO bank_accounts (
            user_id, account_number, currency, opening_balance, is_active
        )
        SELECT
            u.id,
            'MIG-' || UPPER(REPLACE(u.id::text, '-', '')),
            u.currency,
            0,
            TRUE
        FROM users AS u
        WHERE NOT EXISTS (
            SELECT 1 FROM bank_accounts AS ba WHERE ba.user_id = u.id
        )
        """
    )

    # A linked ledger row and purchase represent the same movement. Collapse
    # them only when ownership, amount, and currency agree exactly.
    op.execute(
        """
        UPDATE transactions AS t
        SET
            account_id = bl.account_id,
            direction = bl.direction,
            description = bl.description
        FROM bank_ledger AS bl
        JOIN bank_accounts AS ba ON ba.id = bl.account_id
        WHERE bl.transaction_id = t.id
          AND ba.user_id = t.user_id
          AND bl.amount = t.amount
          AND ba.currency = t.currency
        """
    )

    # Purchases that never had a ledger row belong to the user's oldest active
    # account (falling back to the oldest account if all are inactive).
    op.execute(
        """
        UPDATE transactions AS t
        SET account_id = (
            SELECT ba.id
            FROM bank_accounts AS ba
            WHERE ba.user_id = t.user_id
            ORDER BY ba.is_active DESC, ba.opened_at, ba.id
            LIMIT 1
        )
        WHERE t.account_id IS NULL
        """
    )

    # Preserve standalone ledger credits/debits and any linked row that could
    # not be safely collapsed. Account-only movements have no purchase category.
    op.execute(
        """
        INSERT INTO transactions (
            user_id,
            account_id,
            checkin_id,
            direction,
            amount,
            currency,
            category_code,
            description,
            occurred_at,
            created_at
        )
        SELECT
            ba.user_id,
            bl.account_id,
            NULL,
            bl.direction,
            bl.amount,
            ba.currency,
            NULL,
            bl.description,
            bl.occurred_at,
            bl.occurred_at
        FROM bank_ledger AS bl
        JOIN bank_accounts AS ba ON ba.id = bl.account_id
        WHERE bl.transaction_id IS NULL
           OR NOT EXISTS (
                SELECT 1
                FROM transactions AS t
                WHERE t.id = bl.transaction_id
                  AND t.account_id = bl.account_id
                  AND t.direction = bl.direction
                  AND t.amount = bl.amount
                  AND t.currency = ba.currency
           )
        """
    )

    op.alter_column(
        "transactions", "account_id", existing_type=sa.BigInteger(), nullable=False
    )
    op.drop_table("bank_ledger")


def downgrade() -> None:
    direction_type = postgresql.ENUM(
        *_DIRECTIONS, name="transaction_direction", create_type=False
    )
    op.create_table(
        "bank_ledger",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("direction", direction_type, nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("transaction_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "amount > 0", name=conv("ck_bank_ledger_amount_positive")
        ),
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

    # Every unified movement becomes a ledger row. Only debit purchases remain
    # in the old transactions table; credit/account-only rows live in ledger.
    op.execute(
        """
        INSERT INTO bank_ledger (
            account_id, direction, amount, description, transaction_id, occurred_at
        )
        SELECT
            account_id,
            direction,
            amount,
            description,
            CASE
                WHEN direction = 'debit' AND category_code IS NOT NULL THEN id
                ELSE NULL
            END,
            occurred_at
        FROM transactions
        WHERE amount > 0
        """
    )
    op.execute(
        """
        INSERT INTO bank_ledger (
            account_id, direction, amount, description, transaction_id, occurred_at
        )
        SELECT
            id,
            (
                CASE WHEN opening_balance >= 0 THEN 'credit' ELSE 'debit' END
            )::transaction_direction,
            ABS(opening_balance),
            'Opening balance',
            NULL,
            opened_at
        FROM bank_accounts
        WHERE opening_balance <> 0
        """
    )
    op.execute(
        """
        DELETE FROM transactions
        WHERE direction = 'credit' OR category_code IS NULL
        """
    )

    op.alter_column(
        "transactions", "category_code", existing_type=sa.Text(), nullable=False
    )
    op.drop_index("ix_transactions_account_id_occurred_at", table_name="transactions")
    op.drop_constraint(
        conv("fk_transactions_account_id_bank_accounts"),
        "transactions",
        type_="foreignkey",
    )
    op.drop_column("transactions", "description")
    op.drop_column("transactions", "direction")
    op.drop_column("transactions", "account_id")
    op.drop_column("bank_accounts", "opening_balance")
    op.execute("ALTER TYPE transaction_direction RENAME TO ledger_direction")
