from enum import StrEnum

APP_NAME = "Hawkeye"
APP_TAGLINE = "Report. Track. Respond."


class Roles(StrEnum):
    RESIDENT = "resident"
    AUTHORITY = "authority"
    ADMIN = "admin"


class IncidentStatus(StrEnum):
    """Lifecycle: reported (PENDING) -> verified -> assigned -> in_progress -> resolved -> closed."""

    PENDING = "pending"  # reported
    VERIFIED = "verified"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    CLOSED = "closed"


class LocationMode(StrEnum):
    """How the resident indicated incident location (saved address, current GPS, or other)."""

    SAVED = "saved"
    CURRENT = "current"
    OTHER = "other"


class UrgencyLevel(StrEnum):
    """Resident-facing urgency for guided incident form; maps to severity."""

    URGENT_NOW = "urgent_now"
    NEEDS_ATTENTION_SOON = "soon"
    CAN_BE_SCHEDULED = "scheduled"
