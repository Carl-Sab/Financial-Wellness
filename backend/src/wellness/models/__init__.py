"""SQLAlchemy models.

Deliberately re-exports from wellness.models.financial and
wellness.models.biometrics side by side here — that's fine, this is the single
assembly point Alembic's autogenerate reads metadata from. The boundary that
must never exist is those two modules importing *each other*.
"""

from wellness.models.base import Base
from wellness.models.biometrics import ArousalState, BiometricSample, UserBaseline
from wellness.models.financial import FinancialProfile
from wellness.models.notifications import NotificationFeedback, NotificationOutbox
from wellness.models.users import User, UserConsent, UserProfile

__all__ = [
    "ArousalState",
    "Base",
    "BiometricSample",
    "FinancialProfile",
    "NotificationFeedback",
    "NotificationOutbox",
    "User",
    "UserBaseline",
    "UserConsent",
    "UserProfile",
]
