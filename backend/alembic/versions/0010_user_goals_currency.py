"""add user_goals.currency

Budgets can now be set in USD as well as LBP (see
wellness.services.currency for the fixed 1 USD = 90,000 LBP conversion used
when comparing a goal's target against transactions in a different
currency). Defaults existing rows to 'LBP' to match their prior implicit
currency (user_goals.target_amount always meant LBP before this column
existed).

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_goals",
        sa.Column("currency", sa.Text(), nullable=False, server_default="LBP"),
    )


def downgrade() -> None:
    op.drop_column("user_goals", "currency")
