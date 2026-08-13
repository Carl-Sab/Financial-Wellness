"""add canonical category marketing scores

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.schema import conv

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("categories", sa.Column("marketing_score", sa.REAL(), nullable=True))
    op.execute(
        """
        UPDATE categories
        SET marketing_score = CASE code
            WHEN 'clothing' THEN 1.00
            WHEN 'mall' THEN 1.00
            WHEN 'online' THEN 0.75
            WHEN 'groceries' THEN 0.75
            WHEN 'other' THEN 0.25
            WHEN 'electronics' THEN 0.00
            WHEN 'restaurant' THEN 0.50
            ELSE 0.25
        END
        """
    )
    op.alter_column("categories", "marketing_score", nullable=False)
    op.create_check_constraint(
        conv("ck_categories_marketing_score_range"),
        "categories",
        "marketing_score BETWEEN 0 AND 1",
    )


def downgrade() -> None:
    op.drop_constraint(
        conv("ck_categories_marketing_score_range"), "categories", type_="check"
    )
    op.drop_column("categories", "marketing_score")
