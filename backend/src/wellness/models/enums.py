import enum


class ConsentFeature(enum.StrEnum):
    BIOMETRIC_COLLECTION = "biometric_collection"
    NOTIFICATIONS = "notifications"


class BiometricQualityFlag(enum.StrEnum):
    OK = "ok"
    MOTION_ARTIFACT = "motion_artifact"
    POOR_CONTACT = "poor_contact"
    OFF_BODY = "off_body"


class ArousalLabel(enum.StrEnum):
    CALM = "calm"
    ELEVATED = "elevated"
    HIGH = "high"


class NotificationStatus(enum.StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SUPPRESSED = "suppressed"


class NotificationFeedbackEvent(enum.StrEnum):
    DELIVERED = "delivered"
    OPENED = "opened"
    DISMISSED = "dismissed"
    MARKED_HELPFUL = "marked_helpful"
    MARKED_NOT_NOW = "marked_not_now"
