import enum


class Level3(enum.StrEnum):
    LOW = "low"
    MID = "mid"
    HIGH = "high"


class ValenceLevel(enum.StrEnum):
    VERY_UNPLEASANT = "very_unpleasant"
    UNPLEASANT = "unpleasant"
    NEUTRAL = "neutral"
    PLEASANT = "pleasant"
    VERY_PLEASANT = "very_pleasant"


class OutboxStatus(enum.StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SUPPRESSED = "suppressed"


class FeedbackEvent(enum.StrEnum):
    DELIVERED = "delivered"
    OPENED = "opened"
    DISMISSED = "dismissed"
    MARKED_HELPFUL = "marked_helpful"
    MARKED_NOT_NOW = "marked_not_now"


class TransactionDirection(enum.StrEnum):
    CREDIT = "credit"
    DEBIT = "debit"
