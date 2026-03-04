from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import select

from app.constants import IncidentStatus
from app.extensions import db
from app.models.incident import Incident


class IncidentRepository:
    """Data access helper for Incident entities."""

    def get_by_id(self, incident_id: int) -> Optional[Incident]:
        return db.session.get(Incident, incident_id)

    def add(self, incident: Incident) -> Incident:
        db.session.add(incident)
        return incident

    def list_for_resident(
        self,
        resident_id: int,
    ) -> Iterable[Incident]:
        stmt = (
            select(Incident)
            .where(Incident.reported_by_id == resident_id)
            .order_by(Incident.created_at.desc())
        )
        return db.session.execute(stmt).scalars().all()

    def list_for_authority(
        self,
        status: Optional[IncidentStatus] = None,
    ) -> Iterable[Incident]:
        stmt = select(Incident).order_by(Incident.created_at.desc())
        if status is not None:
            stmt = stmt.where(Incident.status == status.value)
        return db.session.execute(stmt).scalars().all()

