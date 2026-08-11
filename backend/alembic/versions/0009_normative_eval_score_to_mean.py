"""questionnaire_responses: normative_eval_score sum -> mean

Block E now averages its 8 reverse-coded pairs instead of summing them, so
normative_eval_score moves from an 8-40 range to 1-5 — consistent with the
other four scores.

Unlike 0008 (which deleted every existing row because NULL wasn't
recoverable), the existing values here ARE recoverable: a sum of 8 items
each 1-5 converts to their mean by dividing by 8. Existing rows are
converted in place, not deleted.

Order matters: the old CHECK constraint (8-40) has to come off before the
UPDATE, since post-divide values (1-5) would violate it; the new constraint
(1-5) goes on after.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-11
"""

from __future__ import annotations

from alembic import op
from sqlalchemy.schema import conv

# revision identifiers, used by Alembic.
revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        conv("ck_questionnaire_responses_normative_eval_score_range"),
        "questionnaire_responses",
        type_="check",
    )
    op.execute("UPDATE questionnaire_responses SET normative_eval_score = normative_eval_score / 8")
    op.create_check_constraint(
        conv("ck_questionnaire_responses_normative_eval_score_range"),
        "questionnaire_responses",
        "normative_eval_score BETWEEN 1 AND 5",
    )


def downgrade() -> None:
    op.drop_constraint(
        conv("ck_questionnaire_responses_normative_eval_score_range"),
        "questionnaire_responses",
        type_="check",
    )
    op.execute("UPDATE questionnaire_responses SET normative_eval_score = normative_eval_score * 8")
    op.create_check_constraint(
        conv("ck_questionnaire_responses_normative_eval_score_range"),
        "questionnaire_responses",
        "normative_eval_score BETWEEN 8 AND 40",
    )
