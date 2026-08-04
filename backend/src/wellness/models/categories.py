"""Spending category reference data.

Shared, static lookup table referenced by both checkins and transactions. It
carries no arousal or financial logic of its own, so referencing it from
either domain does not cross the boundary documented in transactions.py.
"""

from sqlalchemy import REAL, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from wellness.models.base import Base
from wellness.models.enums import Level3

# values_callable: SQLAlchemy's Enum binds the Python member's .name by
# default ("LOW"), not .value ("low"); our Postgres enum labels are lowercase
# values, so this must be explicit or every insert/read mismatches the type.
level_3_enum = SAEnum(
    Level3, name="level_3", native_enum=True, values_callable=lambda cls: [e.value for e in cls]
)


class Category(Base):
    __tablename__ = "categories"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    identity_level: Mapped[Level3] = mapped_column(level_3_enum, nullable=False)
    price_level: Mapped[Level3] = mapped_column(level_3_enum, nullable=False)
    advertising_level: Mapped[Level3] = mapped_column(level_3_enum, nullable=False)
    distribution_level: Mapped[Level3] = mapped_column(level_3_enum, nullable=False)
    # Derived, 0-1; see schema.sql section 8/10 for the formula and seed UPDATE.
    stimuli_score: Mapped[float | None] = mapped_column(REAL, nullable=True)
