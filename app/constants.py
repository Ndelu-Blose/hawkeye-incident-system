from enum import Enum

APP_NAME = "Hawkeye"
APP_TAGLINE = "Report. Track. Respond."


class Roles(str, Enum):
    RESIDENT = "resident"
    AUTHORITY = "authority"
    ADMIN = "admin"


class IncidentStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
