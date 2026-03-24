"""Analytics repository: incident volume, resolution times, hotspots, authority workload."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from app.constants import IncidentEventType
from app.extensions import db
from app.models.audit_log import AuditLog
from app.models.authority import Authority
from app.models.incident import Incident
from app.models.incident_dispatch import IncidentDispatch
from app.models.incident_event import IncidentEvent
from app.models.incident_ownership_history import IncidentOwnershipHistory


class AnalyticsRepository:
    """Data access for analytics and dashboard metrics."""

    def incident_volume_by_day(
        self,
        since: datetime,
    ) -> list[dict[str, Any]]:
        """Count incidents per day from incident_events (incident_created)."""
        stmt = (
            select(
                func.date(IncidentEvent.created_at).label("day"),
                func.count(IncidentEvent.id).label("count"),
            )
            .where(
                IncidentEvent.event_type == IncidentEventType.INCIDENT_CREATED.value,
                IncidentEvent.created_at >= since,
            )
            .group_by(func.date(IncidentEvent.created_at))
            .order_by(func.date(IncidentEvent.created_at).asc())
        )
        rows = db.session.execute(stmt).all()
        return [{"day": str(r.day), "count": r.count} for r in rows]

    def avg_resolution_time_by_category(
        self,
        since: datetime,
    ) -> list[dict[str, Any]]:
        """Average hours from incident_created to incident_resolved by category (event-backed)."""
        created = (
            select(
                IncidentEvent.incident_id,
                IncidentEvent.created_at.label("created_at"),
            )
            .where(IncidentEvent.event_type == IncidentEventType.INCIDENT_CREATED.value)
            .subquery()
        )
        resolved = (
            select(
                IncidentEvent.incident_id,
                IncidentEvent.created_at.label("resolved_at"),
            )
            .where(
                IncidentEvent.event_type == IncidentEventType.INCIDENT_RESOLVED.value,
                IncidentEvent.created_at >= since,
            )
            .subquery()
        )
        stmt = (
            select(
                Incident.category,
                Incident.category_id,
                func.avg(
                    func.extract("epoch", resolved.c.resolved_at)
                    - func.extract("epoch", created.c.created_at)
                ).label("avg_seconds"),
                func.count(Incident.id).label("count"),
            )
            .select_from(created)
            .join(resolved, created.c.incident_id == resolved.c.incident_id)
            .join(Incident, Incident.id == created.c.incident_id)
            .group_by(Incident.category, Incident.category_id)
            .order_by(func.count(Incident.id).desc())
        )
        rows = db.session.execute(stmt).all()
        return [
            {
                "category": r.category,
                "category_id": r.category_id,
                "avg_hours": round((r.avg_seconds or 0) / 3600, 1),
                "count": r.count,
            }
            for r in rows
        ]

    def avg_dispatch_to_ack_time_by_authority(
        self,
        since: datetime,
    ) -> list[dict[str, Any]]:
        """Average hours from dispatched_at to ack_at by authority (acknowledged dispatches)."""
        stmt = (
            select(
                IncidentDispatch.authority_id,
                Authority.name.label("authority_name"),
                func.avg(
                    func.extract("epoch", IncidentDispatch.ack_at)
                    - func.extract("epoch", IncidentDispatch.dispatched_at)
                ).label("avg_seconds"),
                func.count(IncidentDispatch.id).label("count"),
            )
            .join(Authority, IncidentDispatch.authority_id == Authority.id)
            .where(
                IncidentDispatch.ack_at.isnot(None),
                IncidentDispatch.status == "acknowledged",
                IncidentDispatch.dispatched_at >= since,
            )
            .group_by(IncidentDispatch.authority_id, Authority.name)
            .order_by(func.count(IncidentDispatch.id).desc())
        )
        rows = db.session.execute(stmt).all()
        return [
            {
                "authority_id": r.authority_id,
                "authority_name": r.authority_name,
                "avg_hours": round((r.avg_seconds or 0) / 3600, 1),
                "count": r.count,
            }
            for r in rows
        ]

    def open_incidents_by_authority(
        self,
    ) -> list[dict[str, Any]]:
        """Count open incidents (assigned, acknowledged, in_progress) per authority via ownership_history."""
        open_statuses = [
            "assigned",
            "acknowledged",
            "in_progress",
        ]
        stmt = (
            select(
                IncidentOwnershipHistory.authority_id,
                Authority.name.label("authority_name"),
                func.count(Incident.id).label("open_count"),
            )
            .select_from(IncidentOwnershipHistory)
            .join(Incident, IncidentOwnershipHistory.incident_id == Incident.id)
            .outerjoin(Authority, IncidentOwnershipHistory.authority_id == Authority.id)
            .where(
                IncidentOwnershipHistory.is_current.is_(True),
                Incident.status.in_(open_statuses),
            )
            .group_by(IncidentOwnershipHistory.authority_id, Authority.name)
            .order_by(func.count(Incident.id).desc())
        )
        rows = db.session.execute(stmt).all()
        return [
            {
                "authority_id": r.authority_id,
                "authority_name": r.authority_name or "Unknown",
                "open_count": r.open_count,
            }
            for r in rows
        ]

    def hotspots_by_suburb(
        self,
        since: datetime,
    ) -> list[dict[str, Any]]:
        """Count incidents per suburb_or_ward since the given date (hotspots)."""
        stmt = (
            select(
                Incident.suburb_or_ward,
                func.count(Incident.id).label("count"),
            )
            .where(Incident.reported_at >= since)
            .group_by(Incident.suburb_or_ward)
            .order_by(func.count(Incident.id).desc())
        )
        rows = db.session.execute(stmt).all()
        return [{"suburb_or_ward": r.suburb_or_ward or "Unknown", "count": r.count} for r in rows]

    def total_incidents_this_week(
        self,
        since: datetime,
    ) -> int:
        """Total incidents created since the given date (from incident_events)."""
        stmt = select(func.count(IncidentEvent.id)).where(
            IncidentEvent.event_type == IncidentEventType.INCIDENT_CREATED.value,
            IncidentEvent.created_at >= since,
        )
        result = db.session.execute(stmt).scalar()
        return int(result or 0)

    def resolved_this_week(
        self,
        since: datetime,
    ) -> int:
        """Incidents resolved since the given date (from incident_events)."""
        stmt = select(func.count(IncidentEvent.id)).where(
            IncidentEvent.event_type == IncidentEventType.INCIDENT_RESOLVED.value,
            IncidentEvent.created_at >= since,
        )
        result = db.session.execute(stmt).scalar()
        return int(result or 0)

    def avg_resolution_time_hours(
        self,
        since: datetime,
    ) -> float | None:
        """Overall average resolution time in hours (incident_created -> incident_resolved)."""
        created = (
            select(
                IncidentEvent.incident_id,
                IncidentEvent.created_at.label("created_at"),
            )
            .where(IncidentEvent.event_type == IncidentEventType.INCIDENT_CREATED.value)
            .subquery()
        )
        resolved = (
            select(
                IncidentEvent.incident_id,
                IncidentEvent.created_at.label("resolved_at"),
            )
            .where(
                IncidentEvent.event_type == IncidentEventType.INCIDENT_RESOLVED.value,
                IncidentEvent.created_at >= since,
            )
            .subquery()
        )
        stmt = (
            select(
                func.avg(
                    func.extract("epoch", resolved.c.resolved_at)
                    - func.extract("epoch", created.c.created_at)
                ).label("avg_seconds"),
            )
            .select_from(created)
            .join(resolved, created.c.incident_id == resolved.c.incident_id)
        )
        row = db.session.execute(stmt).mappings().first()
        if row is None or row.get("avg_seconds") is None:
            return None
        return round(row["avg_seconds"] / 3600, 1)

    def rejection_count_by_category(
        self,
        since: datetime,
    ) -> list[dict[str, Any]]:
        """Count rejected incidents by category (from incident_events)."""
        stmt = (
            select(
                Incident.category,
                Incident.category_id,
                func.count(IncidentEvent.id).label("count"),
            )
            .select_from(IncidentEvent)
            .join(Incident, IncidentEvent.incident_id == Incident.id)
            .where(
                IncidentEvent.event_type == IncidentEventType.INCIDENT_REJECTED.value,
                IncidentEvent.created_at >= since,
            )
            .group_by(Incident.category, Incident.category_id)
            .order_by(func.count(IncidentEvent.id).desc())
        )
        rows = db.session.execute(stmt).all()
        return [
            {
                "category": r.category,
                "category_id": r.category_id,
                "count": r.count,
            }
            for r in rows
        ]

    def override_count_by_actor(
        self,
        since: datetime,
    ) -> list[dict[str, Any]]:
        """Count incident_status_override events by actor (from audit_logs)."""
        stmt = (
            select(
                AuditLog.actor_user_id,
                AuditLog.actor_role,
                func.count(AuditLog.id).label("count"),
            )
            .where(
                AuditLog.entity_type == "incident",
                AuditLog.action == "incident_status_override",
                AuditLog.created_at >= since,
            )
            .group_by(AuditLog.actor_user_id, AuditLog.actor_role)
            .order_by(func.count(AuditLog.id).desc())
        )
        rows = db.session.execute(stmt).all()
        return [
            {
                "actor_user_id": r.actor_user_id,
                "actor_role": r.actor_role or "System",
                "count": r.count,
            }
            for r in rows
        ]

    def hotspot_incident_points(
        self,
        *,
        since: datetime,
        statuses: list[str] | None = None,
        category: str | None = None,
        authority_id: int | None = None,
        near_suburb: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return incident points eligible for hotspot analytics."""
        stmt = select(
            Incident.id,
            Incident.latitude,
            Incident.longitude,
            Incident.suburb,
            Incident.ward,
            Incident.suburb_or_ward,
            Incident.status,
            Incident.severity,
            Incident.current_authority_id,
            Incident.category,
            Incident.reported_at,
            Incident.created_at,
        ).where(
            Incident.hotspot_excluded.is_(False),
            Incident.latitude.isnot(None),
            Incident.longitude.isnot(None),
            func.coalesce(Incident.reported_at, Incident.created_at) >= since,
        )
        if statuses:
            stmt = stmt.where(Incident.status.in_(statuses))
        if category:
            stmt = stmt.where(Incident.category == category)
        if authority_id is not None:
            stmt = stmt.where(Incident.current_authority_id == authority_id)
        if near_suburb:
            stmt = stmt.where(
                func.lower(func.coalesce(Incident.suburb, Incident.suburb_or_ward, ""))
                == near_suburb.lower()
            )

        rows = db.session.execute(stmt).all()
        return [
            {
                "id": r.id,
                "latitude": float(r.latitude),
                "longitude": float(r.longitude),
                "suburb": r.suburb,
                "ward": r.ward,
                "suburb_or_ward": r.suburb_or_ward,
                "status": r.status,
                "severity": r.severity,
                "current_authority_id": r.current_authority_id,
                "category": r.category,
                "reported_at": r.reported_at,
                "created_at": r.created_at,
            }
            for r in rows
        ]
