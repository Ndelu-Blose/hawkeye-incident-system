"""Repository for incident_ownership_history."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select as sa_select
from sqlalchemy import update

from app.extensions import db
from app.models.incident_ownership_history import IncidentOwnershipHistory


class IncidentOwnershipRepository:
    """Repository for incident ownership history. Enforces one-current-row rule."""

    def add(self, record: IncidentOwnershipHistory) -> None:
        """Persist an ownership record (caller must commit)."""
        db.session.add(record)

    def close_current(self, incident_id: int, ended_at: datetime | None = None) -> None:
        """Close the current ownership row for an incident. Caller must commit."""
        ended = ended_at or datetime.now(UTC)
        stmt = (
            update(IncidentOwnershipHistory)
            .where(
                IncidentOwnershipHistory.incident_id == incident_id,
                IncidentOwnershipHistory.is_current.is_(True),
            )
            .values(ended_at=ended, is_current=False)
        )
        db.session.execute(stmt)

    def start_ownership(
        self,
        incident_id: int,
        authority_id: int,
        *,
        assigned_by_user_id: int | None = None,
        dispatch_id: int | None = None,
        reason: str | None = None,
    ) -> IncidentOwnershipHistory:
        """Close current (if any) and start new ownership. Caller must commit."""
        self.close_current(incident_id)
        record = IncidentOwnershipHistory(
            incident_id=incident_id,
            authority_id=authority_id,
            assigned_by_user_id=assigned_by_user_id,
            is_current=True,
            dispatch_id=dispatch_id,
            reason=reason,
        )
        self.add(record)
        return record

    def get_current(self, incident_id: int) -> IncidentOwnershipHistory | None:
        """Return the current ownership row for an incident, or None."""
        return db.session.execute(
            sa_select(IncidentOwnershipHistory).where(
                IncidentOwnershipHistory.incident_id == incident_id,
                IncidentOwnershipHistory.is_current.is_(True),
            )
        ).scalar_one_or_none()
