"""questionnaire_responses: add normative_eval_score (Block E)

Block E (normative evaluation) is now a required part of the signup
questionnaire — normative_eval_score is NOT NULL, unlike the four scores
added earlier, which stayed nullable for the original client-scored smoke
CRUD endpoint's sake.

Deliberate one-off: this migration DELETES every existing
questionnaire_responses row before adding the column. As of writing there
were 5 — three were the author's own Playwright verification artifacts from
building Blocks A-D, and two (demo@example.com, cold-start@example.com)
were regenerable seed fixtures from scripts/seed_demo_data.py. None were
real user submissions, so there was nothing worth backfilling a sentinel
for; a fake normative_eval_score would have been indistinguishable from a
real one once written, silently corrupting any later analysis that reads
it. If this migration is ever run against a database with real completed
questionnaires, this delete is NOT what you want — stop and write a real
backfill instead.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.schema import conv

# revision identifiers, used by Alembic.
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM questionnaire_responses")
    op.add_column(
        "questionnaire_responses",
        sa.Column("normative_eval_score", sa.REAL(), nullable=False),
    )
    op.create_check_constraint(
        conv("ck_questionnaire_responses_normative_eval_score_range"),
        "questionnaire_responses",
        "normative_eval_score BETWEEN 8 AND 40",
    )


def downgrade() -> None:
    op.drop_constraint(
        conv("ck_questionnaire_responses_normative_eval_score_range"),
        "questionnaire_responses",
        type_="check",
    )
    op.drop_column("questionnaire_responses", "normative_eval_score")
