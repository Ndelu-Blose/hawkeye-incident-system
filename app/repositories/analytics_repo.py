"""Analytics repository: incident volume, resolution times, hotspots, authority workload."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from app.extensions import db
from app.models.authority import Authority
from app.models.incident import Incident
from app.models.incident_dispatch import IncidentDispatch


class AnalyticsRepository:
    """Data access for analytics and dashboard metrics."""

    def incident_volume_by_day(
        self,
        since: datetime,
    ) -> list[dict[str, Any]]:
        """Count incidents per day since the given date."""
        stmt = (
            select(
                func.date(Incident.reported_at).label("day"),
                func.count(Incident.id).label("count"),
            )
            .where(Incident.reported_at >= since)
            .group_by(func.date(Incident.reported_at))
            .order_by(func.date(Incident.reported_at).asc())
        )
        rows = db.session.execute(stmt).all()
        return [{"day": str(r.day), "count": r.count} for r in rows]

    def avg_resolution_time_by_category(
        self,
        since: datetime,
    ) -> list[dict[str, Any]]:
        """Average hours from reported_at to resolved_at by category (resolved incidents only)."""
        stmt = (
            select(
                Incident.category,
                Incident.category_id,
                func.avg(
                    func.extract("epoch", Incident.resolved_at)
                    - func.extract("epoch", Incident.reported_at)
                ).label("avg_seconds"),
                func.count(Incident.id).label("count"),
            )
            .where(
                Incident.resolved_at.isnot(None),
                Incident.reported_at.isnot(None),
                Incident.resolved_at >= since,
            )
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
                IncidentDispatch.ack_status == "acknowledged",
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
        """Count open incidents (reported, screened, assigned, in_progress) per authority."""
        open_statuses = [
            "reported",
            "screened",
            "assigned",
            "in_progress",
        ]
        stmt = (
            select(
                Incident.current_authority_id,
                Authority.name.label("authority_name"),
                func.count(Incident.id).label("open_count"),
            )
            .outerjoin(Authority, Incident.current_authority_id == Authority.id)
            .where(
                Incident.status.in_(open_statuses),
                Incident.current_authority_id.isnot(None),
            )
            .group_by(Incident.current_authority_id, Authority.name)
            .order_by(func.count(Incident.id).desc())
        )
        rows = db.session.execute(stmt).all()
        return [
            {
                "authority_id": r.current_authority_id,
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
        """Total incidents reported since the given date."""
        result = (
            db.session.query(func.count(Incident.id)).where(Incident.reported_at >= since).scalar()
        )
        return result or 0

    def resolved_this_week(
        self,
        since: datetime,
    ) -> int:
        """Incidents resolved since the given date."""
        result = (
            db.session.query(func.count(Incident.id))
            .where(
                Incident.resolved_at >= since,
                Incident.resolved_at.isnot(None),
            )
            .scalar()
        )
        return result or 0

    def avg_resolution_time_hours(
        self,
        since: datetime,
    ) -> float | None:
        """Overall average resolution time in hours (reported -> resolved)."""
        stmt = select(
            func.avg(
                func.extract("epoch", Incident.resolved_at)
                - func.extract("epoch", Incident.reported_at)
            ).label("avg_seconds"),
        ).where(
            Incident.resolved_at.isnot(None),
            Incident.reported_at.isnot(None),
            Incident.resolved_at >= since,
        )
        row = db.session.execute(stmt).mappings().first()
        if row is None or row.get("avg_seconds") is None:
            return None
        return round(row["avg_seconds"] / 3600, 1)
