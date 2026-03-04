from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func

from app.constants import IncidentStatus
from app.extensions import db
from app.models.incident import Incident


@dataclass
class DashboardOverview:
    total_incidents: int
    pending: int
    in_progress: int
    resolved: int


class DashboardService:
    """Aggregate metrics for admin/authority dashboards."""

    def get_overview(self) -> DashboardOverview:
        total = db.session.query(func.count(Incident.id)).scalar() or 0

        def _count_for(status: IncidentStatus) -> int:
            return (
                db.session.query(func.count(Incident.id))
                .filter(Incident.status == status.value)
                .scalar()
                or 0
            )

        return DashboardOverview(
            total_incidents=total,
            pending=_count_for(IncidentStatus.PENDING),
            in_progress=_count_for(IncidentStatus.IN_PROGRESS),
            resolved=_count_for(IncidentStatus.RESOLVED),
        )


dashboard_service = DashboardService()

