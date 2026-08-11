"""questionnaire_responses: unique(user_id)

The signup questionnaire runs at most once per user. POST
/api/v1/questionnaire relies on this constraint (IntegrityError -> 409) to
make "already completed" a race-safe guarantee rather than an
application-level check-then-insert two concurrent submissions could both
slip past.

Also drops ix_questionnaire_responses_user_id_completed_at: a unique
constraint on user_id gets its own backing index automatically, and with at
most one row per user the completed_at ordering component of the old
composite index was never going to have anything to order — pure write
overhead once the previous migration's constraint is in place.

Constraint name is wrapped in sa.schema.conv() so it matches exactly what
wellness.models' naming convention generates — see the note in 0004.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.schema import conv

# revision identifiers, used by Alembic.
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(
        "ix_questionnaire_responses_user_id_completed_at", table_name="questionnaire_responses"
    )
    op.create_unique_constraint(
        conv("uq_questionnaire_responses_user_id"), "questionnaire_responses", ["user_id"]
    )


def downgrade() -> None:
    op.drop_constraint(
        conv("uq_questionnaire_responses_user_id"), "questionnaire_responses", type_="unique"
    )
    op.create_index(
        "ix_questionnaire_responses_user_id_completed_at",
        "questionnaire_responses",
        ["user_id", sa.desc("completed_at")],
    )
