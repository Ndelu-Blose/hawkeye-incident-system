from __future__ import annotations

from typing import Iterable

from sqlalchemy import select

from app.extensions import db
from app.models.incident_update import IncidentUpdate


class IncidentUpdateRepository:
    """Data access helper for IncidentUpdate entities."""

    def add(self, update: IncidentUpdate) -> IncidentUpdate:
        db.session.add(update)
        return update

    def list_for_incident(self, incident_id: int) -> Iterable[IncidentUpdate]:
        stmt = (
            select(IncidentUpdate)
            .where(IncidentUpdate.incident_id == incident_id)
            .order_by(IncidentUpdate.created_at.asc())
        )
        return db.session.execute(stmt).scalars().all()

