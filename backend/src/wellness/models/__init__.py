"""SQLAlchemy models.

Deliberately re-exports from every domain module side by side here. This is
the single assembly point Alembic's autogenerate reads metadata from. The
check-in domain and spending domain must not import each other. See the
boundary comment at the top of transactions.py.
"""

from wellness.models.auth import LoginFailure, RefreshToken
from wellness.models.banking import BankAccount
from wellness.models.base import Base
from wellness.models.categories import Category
from wellness.models.checkins import Checkin
from wellness.models.financial import FinancialProfile
from wellness.models.goals import UserGoal
from wellness.models.normalization_snapshots import UserNormalizationSnapshot
from wellness.models.notifications import NotificationFeedback, NotificationOutbox
from wellness.models.transactions import Transaction
from wellness.models.users import QuestionnaireResponse, User

__all__ = [
    "BankAccount",
    "Base",
    "Category",
    "Checkin",
    "FinancialProfile",
    "LoginFailure",
    "NotificationFeedback",
    "NotificationOutbox",
    "QuestionnaireResponse",
    "RefreshToken",
    "Transaction",
    "User",
    "UserGoal",
    "UserNormalizationSnapshot",
]
