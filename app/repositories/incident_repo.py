from __future__ import annotations

from datetime import UTC, datetime, timedelta

from collections.abc import Iterable

from sqlalchemy import select

from app.constants import IncidentStatus
from app.extensions import db
from app.models.incident import Incident


class IncidentRepository:
    """Data access helper for Incident entities."""

    def get_by_id(self, incident_id: int) -> Incident | None:
        return db.session.get(Incident, incident_id)

    def add(self, incident: Incident) -> Incident:
        db.session.add(incident)
        return incident

    def list_for_resident(
        self,
        resident_id: int,
        status: IncidentStatus | None = None,
    ) -> Iterable[Incident]:
        stmt = (
            select(Incident)
            .where(Incident.reported_by_id == resident_id)
            .order_by(Incident.created_at.desc())
        )
        if status is not None:
            stmt = stmt.where(Incident.status == status.value)
        return db.session.execute(stmt).scalars().all()

    def find_recent_similar(
        self,
        category: str,
        suburb_or_ward: str,
        hours: int = 24,
        limit: int = 5,
    ) -> list[Incident]:
        since = datetime.now(UTC) - timedelta(hours=hours)
        stmt = (
            select(Incident)
            .where(Incident.category == category)
            .where(Incident.suburb_or_ward == suburb_or_ward)
            .where(Incident.created_at >= since)
            .order_by(Incident.created_at.desc())
            .limit(limit)
        )
        return list(db.session.execute(stmt).scalars().all())

    def list_for_authority(
        self,
        status: IncidentStatus | None = None,
    ) -> Iterable[Incident]:
        stmt = select(Incident).order_by(Incident.created_at.desc())
        if status is not None:
            stmt = stmt.where(Incident.status == status.value)
        return db.session.execute(stmt).scalars().all()
