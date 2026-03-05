from __future__ import annotations

from collections.abc import Iterable

from app.constants import IncidentStatus
from app.extensions import db
from app.models.incident import Incident
from app.models.incident_update import IncidentUpdate
from app.models.user import User
from app.repositories.incident_repo import IncidentRepository
from app.repositories.incident_update_repo import IncidentUpdateRepository
from app.services.notification_service import notification_service


class IncidentService:
    """Business logic for the incident lifecycle."""

    def __init__(
        self,
        incident_repo: IncidentRepository | None = None,
        update_repo: IncidentUpdateRepository | None = None,
    ) -> None:
        self.incident_repo = incident_repo or IncidentRepository()
        self.update_repo = update_repo or IncidentUpdateRepository()

    def create_incident(
        self,
        payload: dict,
        resident_user: User,
    ) -> tuple[Incident | None, list[str]]:
        errors: list[str] = []

        title = (payload.get("title") or "").strip()
        description = (payload.get("description") or "").strip()
        category = (payload.get("category") or "").strip()
        location = (payload.get("location") or "").strip()
        severity = (payload.get("severity") or "").strip()

        if not title:
            errors.append("Title is required.")
        if not description:
            errors.append("Description is required.")
        if not category:
            errors.append("Category is required.")
        if not location:
            errors.append("Location is required.")
        if not severity:
            errors.append("Severity is required.")

        if errors:
            return None, errors

        incident = Incident(
            reported_by_id=resident_user.id,
            title=title,
            description=description,
            category=category,
            location=location,
            severity=severity,
            status=IncidentStatus.PENDING.value,
        )
        self.incident_repo.add(incident)

        update = IncidentUpdate(
            incident=incident,
            updated_by_id=resident_user.id,
            from_status=None,
            to_status=IncidentStatus.PENDING.value,
            note="Incident created",
        )
        self.update_repo.add(update)

        # In Phase 3 this will target authority/admin users from configuration.
        # For now, the service only creates the NotificationLog rows when called.
        # Consumers can decide which recipients to pass in.

        db.session.commit()
        return incident, errors

    def get_incident_with_history(
        self,
        incident_id: int,
        user: User,
    ) -> tuple[Incident | None, list[IncidentUpdate]]:
        incident = self.incident_repo.get_by_id(incident_id)
        if incident is None:
            return None, []

        # For now, access control is handled at the route level.
        updates = list(self.update_repo.list_for_incident(incident_id))
        return incident, updates

    def list_incidents_for_resident(self, user: User) -> Iterable[Incident]:
        return self.incident_repo.list_for_resident(user.id)

    def list_incidents_for_authority(
        self,
        status: IncidentStatus | None = None,
    ) -> Iterable[Incident]:
        return self.incident_repo.list_for_authority(status=status)

    def update_status(
        self,
        incident_id: int,
        to_status: IncidentStatus,
        note: str,
        authority_user: User,
    ) -> tuple[bool, list[str]]:
        errors: list[str] = []
        incident = self.incident_repo.get_by_id(incident_id)
        if incident is None:
            errors.append("Incident not found.")
            return False, errors

        current_status = IncidentStatus(incident.status)
        if current_status == to_status:
            errors.append("Incident is already in that status.")
            return False, errors

        if not self._is_valid_transition(current_status, to_status):
            errors.append("Invalid status transition.")
            return False, errors

        from_status = incident.status
        incident.status = to_status.value
        incident.version += 1

        update = IncidentUpdate(
            incident_id=incident.id,
            updated_by_id=authority_user.id,
            from_status=from_status,
            to_status=to_status.value,
            note=note.strip() or None,
        )
        self.update_repo.add(update)

        notification_service.enqueue_status_changed(
            incident=incident,
            resident=incident.reporter,
        )

        db.session.commit()
        return True, errors

    @staticmethod
    def _is_valid_transition(
        current: IncidentStatus,
        target: IncidentStatus,
    ) -> bool:
        if current == IncidentStatus.PENDING and target in {
            IncidentStatus.IN_PROGRESS,
            IncidentStatus.RESOLVED,
        }:
            return True
        if current == IncidentStatus.IN_PROGRESS and target in {
            IncidentStatus.RESOLVED,
        }:
            return True
        return False


incident_service = IncidentService()
