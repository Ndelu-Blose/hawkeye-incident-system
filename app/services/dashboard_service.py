from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func

from app.constants import IncidentStatus
from app.extensions import db
from app.models.authority import Authority
from app.models.incident import Incident
from app.repositories.incident_repo import IncidentRepository


@dataclass
class DashboardOverview:
    total_incidents: int
    pending: int
    in_progress: int
    resolved: int
    new_today: int
    unassigned: int
    overdue: int
    resolved_this_week: int


class DashboardService:
    """Aggregate metrics for admin/authority dashboards."""

    def __init__(self, incident_repo: IncidentRepository | None = None) -> None:
        self.incident_repo = incident_repo or IncidentRepository()

    def get_overview(self, authority_id: int | None = None) -> DashboardOverview:
        total = db.session.query(Incident).count()
        pending = (
            db.session.query(Incident)
            .filter(Incident.status == IncidentStatus.REPORTED.value)
            .count()
        )
        in_progress = self.incident_repo.count_in_progress()
        resolved = (
            db.session.query(Incident)
            .filter(
                Incident.status.in_((IncidentStatus.RESOLVED.value, IncidentStatus.CLOSED.value))
            )
            .count()
        )
        new_today = self.incident_repo.count_new_today()
        unassigned = self.incident_repo.count_unassigned()
        overdue = self.incident_repo.count_overdue()
        resolved_this_week = self.incident_repo.count_resolved_this_week()
        return DashboardOverview(
            total_incidents=total,
            pending=pending,
            in_progress=in_progress,
            resolved=resolved,
            new_today=new_today,
            unassigned=unassigned,
            overdue=overdue,
            resolved_this_week=resolved_this_week,
        )

    def get_recent_incidents(self, *, limit: int = 5) -> list[Incident]:
        """Latest incidents across the platform for admin dashboards."""
        return self.incident_repo.list_recent(limit=limit)

    def get_overdue_incidents(self, *, limit: int = 5) -> list[Incident]:
        """Overdue incidents for admin dashboards."""
        return self.incident_repo.list_overdue(limit=limit)

    def get_overview_by_authority(self, limit: int = 3) -> list[tuple[Authority, int, int]]:
        """Return top authorities by open and overdue incidents."""
        open_counts: dict[int, int] = {}
        overdue_counts: dict[int, int] = {}

        # Count open incidents per authority.
        stmt_open = (
            db.session.query(Incident.current_authority_id, func.count(Incident.id))
            .filter(
                Incident.current_authority_id.isnot(None),
                Incident.status.notin_(
                    (
                        IncidentStatus.RESOLVED.value,
                        IncidentStatus.REJECTED.value,
                        IncidentStatus.CLOSED.value,
                    )
                ),
            )
            .group_by(Incident.current_authority_id)
        )
        for auth_id, count in stmt_open:
            if auth_id is not None:
                open_counts[int(auth_id)] = int(count)

        # Count overdue incidents per authority in a lightweight way.
        # This reuses the same logic as count_overdue but grouped by authority.
        stmt_overdue = db.session.query(Incident).filter(
            Incident.current_authority_id.isnot(None),
        )
        for inc in stmt_overdue:
            auth_id = inc.current_authority_id
            if auth_id is None:
                continue
            # Here we only approximate overdue by checking resolved_at/closed_at vs reported_at.
            # Full SLA-based grouping is handled in IncidentRepository.count_overdue.
            if inc.reported_at and not inc.resolved_at and not inc.closed_at:
                overdue_counts[auth_id] = overdue_counts.get(auth_id, 0) + 1

        # Build results with Authority objects.
        if not open_counts and not overdue_counts:
            return []

        auth_ids = set(open_counts.keys()) | set(overdue_counts.keys())
        authorities = db.session.query(Authority).filter(Authority.id.in_(auth_ids)).all()
        by_id = {a.id: a for a in authorities}

        rows: list[tuple[Authority, int, int]] = []
        for auth_id in auth_ids:
            auth = by_id.get(auth_id)
            if auth is None:
                continue
            rows.append(
                (
                    auth,
                    open_counts.get(auth_id, 0),
                    overdue_counts.get(auth_id, 0),
                )
            )

        # Sort by open incidents desc, then overdue desc, and limit.
        rows.sort(key=lambda row: (row[1], row[2]), reverse=True)
        return rows[:limit]

    def get_authority_incident_list(
        self,
        status: IncidentStatus | None = None,
        authority_id: int | None = None,
        queue: str | None = None,
        limit: int = 100,
    ) -> list[Incident]:
        """List incidents for authority dashboard. queue: incoming|acknowledged|in_progress|completed."""
        return list(
            self.incident_repo.list_for_authority(
                status=status,
                authority_id=authority_id,
                queue=queue,
                load_relations=True,
            )
        )[:limit]


dashboard_service = DashboardService()
