"""Per-user, per-metric physiological baselines.

Arousal-scoring domain. Nothing here may import from wellness.models.transactions
or wellness.models.financial — see the boundary comment at the top of
transactions.py.

Mean and standard deviation per user per metric, computed across that user's
check-in history and refreshed after each new check-in. This is what makes a
reading interpretable: 82 bpm means nothing until you know that this person's
own mean is 71 with an sd of 6.

sample_n matters: with fewer than about 8 check-ins the standard deviation is
unstable and should not be used for scoring.
"""

import uuid
from datetime import datetime

from sqlalchemy import REAL, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from wellness.models.base import Base


class UserBaseline(Base):
    __tablename__ = "user_baseline"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # One of: heart_rate, hrv_ms, eda_microsiemens, spo2_percent, skin_temp_c.
    metric: Mapped[str] = mapped_column(Text, primary_key=True)
    mean_value: Mapped[float] = mapped_column(REAL, nullable=False)
    sd_value: Mapped[float | None] = mapped_column(REAL, nullable=True)
    sample_n: Mapped[int] = mapped_column(Integer, nullable=False)
    min_value: Mapped[float | None] = mapped_column(REAL, nullable=True)
    max_value: Mapped[float | None] = mapped_column(REAL, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
