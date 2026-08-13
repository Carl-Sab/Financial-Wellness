"""remove merchant and planned fields from transactions

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("transactions", "was_planned")
    op.drop_column("transactions", "merchant_name")


def downgrade() -> None:
    op.add_column("transactions", sa.Column("merchant_name", sa.Text(), nullable=True))
    op.add_column("transactions", sa.Column("was_planned", sa.Boolean(), nullable=True))
