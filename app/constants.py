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
