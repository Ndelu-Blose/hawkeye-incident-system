from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.constants import IncidentStatus
from app.extensions import db
from app.models.incident import Incident


def _start_of_today_utc() -> datetime:
    return datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def _start_of_week_utc() -> datetime:
    now = datetime.now(UTC)
    return (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


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

    # In future this repository can grow methods that leverage the new
    # latitude/longitude fields for radius-based similarity or GIS queries.

    def list_for_authority(
        self,
        status: IncidentStatus | None = None,
        authority_id: int | None = None,
        load_relations: bool = False,
    ) -> Iterable[Incident]:
        stmt = select(Incident).order_by(Incident.created_at.desc())
        if status is not None:
            stmt = stmt.where(Incident.status == status.value)
        if authority_id is not None:
            stmt = stmt.where(Incident.current_authority_id == authority_id)
        if load_relations:
            stmt = stmt.options(
                joinedload(Incident.category_rel),
                joinedload(Incident.location_rel),
                joinedload(Incident.current_authority),
            )
        return db.session.execute(stmt).scalars().unique().all()

    def count_new_today(self) -> int:
        since = _start_of_today_utc()
        stmt = select(func.count(Incident.id)).where(
            (Incident.reported_at >= since) | (Incident.created_at >= since)
        )
        return db.session.execute(stmt).scalar() or 0

    def count_unassigned(self) -> int:
        closed_statuses = (
            IncidentStatus.RESOLVED.value,
            IncidentStatus.REJECTED.value,
            IncidentStatus.CLOSED.value,
        )
        stmt = select(func.count(Incident.id)).where(
            Incident.current_authority_id.is_(None),
            Incident.status.notin_(closed_statuses),
        )
        return db.session.execute(stmt).scalar() or 0

    def count_in_progress(self) -> int:
        stmt = select(func.count(Incident.id)).where(
            Incident.status.in_((IncidentStatus.IN_PROGRESS.value, IncidentStatus.ASSIGNED.value))
        )
        return db.session.execute(stmt).scalar() or 0

    def count_resolved_this_week(self) -> int:
        since = _start_of_week_utc()
        stmt = select(func.count(Incident.id)).where(
            Incident.status.in_((IncidentStatus.RESOLVED.value, IncidentStatus.CLOSED.value)),
            Incident.resolved_at >= since,
        )
        return db.session.execute(stmt).scalar() or 0

    def count_overdue(self) -> int:
        """Incidents not resolved/rejected/closed and past SLA (reported_at + category default_sla_hours)."""
        from app.models import IncidentCategory

        closed_statuses = (
            IncidentStatus.RESOLVED.value,
            IncidentStatus.REJECTED.value,
            IncidentStatus.CLOSED.value,
        )
        now = datetime.now(UTC)
        stmt = (
            select(Incident)
            .outerjoin(IncidentCategory, Incident.category_id == IncidentCategory.id)
            .where(Incident.status.notin_(closed_statuses))
            .where(Incident.reported_at.isnot(None))
            .options(joinedload(Incident.category_rel))
        )
        incidents = [
            row[0] if isinstance(row, tuple) else row
            for row in db.session.execute(stmt).scalars().unique().all()
        ]
        count = 0
        for inc in incidents:
            reported_at = inc.reported_at
            if reported_at is None:
                continue
            if reported_at.tzinfo is None:
                reported_at = reported_at.replace(tzinfo=UTC)
            sla_hours = 72
            if inc.category_rel is not None and inc.category_rel.default_sla_hours is not None:
                sla_hours = inc.category_rel.default_sla_hours
            elif inc.category_id:
                cat = db.session.get(IncidentCategory, inc.category_id)
                if cat and cat.default_sla_hours is not None:
                    sla_hours = cat.default_sla_hours
            due = reported_at + timedelta(hours=sla_hours)
            if due < now:
                count += 1
        return count
