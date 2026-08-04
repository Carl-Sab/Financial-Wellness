"""SQLAlchemy models.

Deliberately re-exports from every domain module side by side here — that's
fine, this is the single assembly point Alembic's autogenerate reads
metadata from. The boundary that must never exist is the arousal-scoring
domain (checkins, baseline, arousal) and the spending domain (transactions,
financial) importing *each other*. See the boundary comment at the top of
transactions.py.
"""

from wellness.models.arousal import ArousalState
from wellness.models.banking import BankAccount, BankLedger
from wellness.models.base import Base
from wellness.models.baseline import UserBaseline
from wellness.models.categories import Category
from wellness.models.checkins import Checkin
from wellness.models.financial import FinancialProfile
from wellness.models.goals import UserGoal
from wellness.models.notifications import NotificationFeedback, NotificationOutbox, UserSettings
from wellness.models.transactions import Transaction
from wellness.models.users import QuestionnaireResponse, User

__all__ = [
    "ArousalState",
    "BankAccount",
    "BankLedger",
    "Base",
    "Category",
    "Checkin",
    "FinancialProfile",
    "NotificationFeedback",
    "NotificationOutbox",
    "QuestionnaireResponse",
    "Transaction",
    "User",
    "UserBaseline",
    "UserGoal",
    "UserSettings",
]
