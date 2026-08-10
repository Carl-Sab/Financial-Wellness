"""allow 'daily' in user_goals.period

Adds 'daily' as a valid value for user_goals.period, used by the
mood-spending analysis endpoint's budget resolution (see
wellness/services/analysis.py: an active period='daily' goal is the
highest-priority source for a user's daily budget).

user_goals.period has never had a database-level CHECK constraint — it is a
plain TEXT column; its allowed values were documented only in a comment on
the model (wellness/models/goals.py) and were never enforced at the SQL
layer. There is nothing to ALTER here. The validation this migration is
named for is added at the Pydantic schema layer instead (see
wellness/schemas/goals.py), which is the layer that actually restricted
`period` to a fixed set of values in the first place.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-08
"""

from __future__ import annotations

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No CHECK constraint exists on user_goals.period to update — see the
    # module docstring. Nothing to do at the DDL level.
    pass


def downgrade() -> None:
    pass
