"""wire biometric_samples into baseline and arousal scoring

Adds user_baseline.source ('samples' | 'checkins') recording whether that
row's mean/sd/sample_n came from biometric_samples or checkins — see
wellness/services/baseline.py.

Adds arousal_state.window_sample_count and .reading_source, recording
whether score_checkin() used the 15-minute biometric_samples window average
or the typed check-in value — see wellness/services/arousal.py.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_baseline",
        sa.Column("source", sa.Text(), server_default="checkins", nullable=False),
    )
    op.add_column(
        "arousal_state",
        sa.Column(
            "window_sample_count", sa.SmallInteger(), server_default="0", nullable=False
        ),
    )
    op.add_column(
        "arousal_state",
        sa.Column("reading_source", sa.Text(), server_default="checkins", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("arousal_state", "reading_source")
    op.drop_column("arousal_state", "window_sample_count")
    op.drop_column("user_baseline", "source")
