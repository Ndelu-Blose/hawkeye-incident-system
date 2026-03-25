from enum import StrEnum

APP_NAME = "Alertweb Solutions"
APP_TAGLINE = "Modern incident reporting and response."


class Roles(StrEnum):
    RESIDENT = "resident"
    AUTHORITY = "authority"
    ADMIN = "admin"


class IncidentStatus(StrEnum):
    """Lifecycle: reported -> screened -> assigned -> acknowledged -> in_progress -> resolved -> closed."""

    REPORTED = "reported"
    AWAITING_EVIDENCE = "awaiting_evidence"
    SCREENED = "screened"
    ASSIGNED = "assigned"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    CLOSED = "closed"


class IncidentEventType(StrEnum):
    """Controlled event type constants for incident_events ledger."""

    INCIDENT_CREATED = "incident_created"
    INCIDENT_SCREENED = "incident_screened"
    INCIDENT_ASSIGNED = "incident_assigned"
    INCIDENT_ACKNOWLEDGED = "incident_acknowledged"
    STATUS_CHANGED = "status_changed"
    INCIDENT_RESOLVED = "incident_resolved"
    INCIDENT_CLOSED = "incident_closed"
    INCIDENT_REJECTED = "incident_rejected"
    OWNERSHIP_CHANGED = "ownership_changed"
    DISPATCH_CREATED = "dispatch_created"
    DISPATCH_DELIVERED = "dispatch_delivered"
    EVIDENCE_UPLOADED = "evidence_uploaded"
    PROOF_REQUESTED = "proof_requested"
    AUTHORITY_PROGRESS_UPDATE = "authority_progress_update"
    AUTHORITY_RESOLUTION_UPDATE = "authority_resolution_update"
    MANUAL_OVERRIDE = "manual_override"
    ROUTE_SUGGESTED = "route_suggested"
    ROUTE_APPLIED = "route_applied"
    ROUTING_FAILED = "routing_failed"
    ROUTING_OVERRIDDEN = "routing_overridden"


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
