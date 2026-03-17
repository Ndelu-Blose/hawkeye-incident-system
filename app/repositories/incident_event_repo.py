"""Repository for incident_events ledger."""

from __future__ import annotations

from sqlalchemy import select

from app.extensions import db
from app.models.incident_event import IncidentEvent


class IncidentEventRepository:
    """Repository for immutable incident event records."""

    def add(self, event: IncidentEvent) -> None:
        """Persist an event (caller must commit)."""
        db.session.add(event)

    def create(
        self,
        incident_id: int,
        event_type: str,
        *,
        from_status: str | None = None,
        to_status: str | None = None,
        actor_user_id: int | None = None,
        actor_role: str | None = None,
        authority_id: int | None = None,
        dispatch_id: int | None = None,
        reason: str | None = None,
        note: str | None = None,
        metadata_json: dict | None = None,
    ) -> IncidentEvent:
        """Create and add an event. Caller must commit."""
        event = IncidentEvent(
            incident_id=incident_id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            authority_id=authority_id,
            dispatch_id=dispatch_id,
            reason=reason,
            note=note,
            metadata_json=metadata_json,
        )
        self.add(event)
        return event

    def list_for_incident(self, incident_id: int) -> list[IncidentEvent]:
        """Return all events for an incident, ordered by created_at."""
        stmt = (
            select(IncidentEvent)
            .where(IncidentEvent.incident_id == incident_id)
            .order_by(IncidentEvent.created_at.asc())
        )
        return list(db.session.execute(stmt).scalars().all())
