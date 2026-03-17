from enum import StrEnum

APP_NAME = "Alertweb Solutions"
APP_TAGLINE = "Modern incident reporting and response."


class Roles(StrEnum):
    RESIDENT = "resident"
    AUTHORITY = "authority"
    ADMIN = "admin"


class IncidentStatus(StrEnum):
    """Lifecycle: reported -> screened -> assigned -> in_progress -> resolved -> closed."""

    REPORTED = "reported"
    SCREENED = "screened"
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
