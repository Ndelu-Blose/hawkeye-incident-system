from __future__ import annotations

from dataclasses import dataclass

from app.constants import IncidentStatus
from app.extensions import db
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
            .filter(Incident.status == IncidentStatus.PENDING.value)
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

    def get_authority_incident_list(
        self,
        status: IncidentStatus | None = None,
        authority_id: int | None = None,
        limit: int = 100,
    ) -> list[Incident]:
        """List incidents for authority dashboard with category, location, authority loaded."""
        return list(
            self.incident_repo.list_for_authority(
                status=status,
                authority_id=authority_id,
                load_relations=True,
            )
        )[:limit]


dashboard_service = DashboardService()
