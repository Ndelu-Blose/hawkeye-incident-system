from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from app.constants import IncidentStatus
from app.extensions import db
from app.models.incident import Incident
from app.models.incident_update import IncidentUpdate
from app.models.user import User
from app.repositories.incident_repo import IncidentRepository
from app.repositories.incident_update_repo import IncidentUpdateRepository
from app.services.notification_service import notification_service
from app.utils.uploads import save_incident_media

if TYPE_CHECKING:
    from werkzeug.datastructures import FileStorage


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
        files: list[FileStorage] | None = None,
    ) -> tuple[Incident | None, list[str]]:
        errors: list[str] = []

        title = (payload.get("title") or "").strip()
        description = (payload.get("description") or "").strip()
        category = (payload.get("category") or "").strip()
        suburb_or_ward = (payload.get("suburb_or_ward") or "").strip()
        street_or_landmark = (payload.get("street_or_landmark") or "").strip()
        nearest_place = (payload.get("nearest_place") or "").strip() or None
        severity = (payload.get("severity") or "").strip()

        if not title:
            errors.append("Title is required.")
        if not description:
            errors.append("Description is required.")
        if not category:
            errors.append("Category is required.")
        if not suburb_or_ward:
            errors.append("Suburb/ward is required.")
        if not street_or_landmark:
            errors.append("Street/landmark is required.")
        if not severity:
            errors.append("Severity is required.")

        if errors:
            return None, errors

        location = f"{street_or_landmark}, {suburb_or_ward}"
        incident = Incident(
            reported_by_id=resident_user.id,
            title=title,
            description=description,
            category=category,
            suburb_or_ward=suburb_or_ward,
            street_or_landmark=street_or_landmark,
            nearest_place=nearest_place,
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
        db.session.flush()

        file_list = list(files) if files else []
        if not file_list:
            errors.append("At least one evidence image is required.")
            db.session.rollback()
            return None, errors
        created_media, media_errors = save_incident_media(incident, file_list)
        errors.extend(media_errors)
        if not created_media:
            if not media_errors:
                errors.append("No valid images could be saved.")
            db.session.rollback()
            return None, errors
        if created_media:
            evidence_update = IncidentUpdate(
                incident_id=incident.id,
                updated_by_id=resident_user.id,
                from_status=IncidentStatus.PENDING.value,
                to_status=IncidentStatus.PENDING.value,
                note="Evidence uploaded",
            )
            self.update_repo.add(evidence_update)
        db.session.commit()
        return incident, []

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

    def list_incidents_for_resident(
        self,
        user: User,
        status: IncidentStatus | None = None,
    ) -> Iterable[Incident]:
        return self.incident_repo.list_for_resident(user.id, status=status)

    def suggest_similar_for_resident(
        self,
        category: str,
        suburb_or_ward: str,
        hours: int = 24,
    ) -> list[Incident]:
        return self.incident_repo.find_recent_similar(
            category=category,
            suburb_or_ward=suburb_or_ward,
            hours=hours,
        )

    @staticmethod
    def can_resident_edit(incident: Incident, user: User) -> bool:
        """True if the resident is the reporter and status is Pending (Option B)."""
        return (
            incident.reported_by_id == user.id and incident.status == IncidentStatus.PENDING.value
        )

    def update_incident_by_resident(
        self,
        incident_id: int,
        resident: User,
        payload: dict,
    ) -> tuple[Incident | None, list[str]]:
        errors: list[str] = []
        incident = self.incident_repo.get_by_id(incident_id)
        if incident is None:
            errors.append("Incident not found.")
            return None, errors
        if incident.reported_by_id != resident.id:
            errors.append("You do not have permission to edit this incident.")
            return None, errors
        if incident.status != IncidentStatus.PENDING.value:
            errors.append("Only pending incidents can be edited.")
            return None, errors

        title = (payload.get("title") or "").strip()
        description = (payload.get("description") or "").strip()
        category = (payload.get("category") or "").strip()
        suburb_or_ward = (payload.get("suburb_or_ward") or "").strip()
        street_or_landmark = (payload.get("street_or_landmark") or "").strip()
        severity = (payload.get("severity") or "").strip()
        nearest_place = (payload.get("nearest_place") or "").strip() or None

        if not title:
            errors.append("Title is required.")
        if not description:
            errors.append("Description is required.")
        if not category:
            errors.append("Category is required.")
        if not suburb_or_ward:
            errors.append("Suburb/ward is required.")
        if not street_or_landmark:
            errors.append("Street/landmark is required.")
        if not severity:
            errors.append("Severity is required.")
        if errors:
            return None, errors

        incident.title = title
        incident.description = description
        incident.category = category
        incident.suburb_or_ward = suburb_or_ward
        incident.street_or_landmark = street_or_landmark
        incident.nearest_place = nearest_place
        incident.location = f"{street_or_landmark}, {suburb_or_ward}"
        incident.severity = severity
        incident.version += 1

        self.update_repo.add(
            IncidentUpdate(
                incident_id=incident.id,
                updated_by_id=resident.id,
                from_status=incident.status,
                to_status=incident.status,
                note="Incident edited by resident",
            )
        )
        db.session.commit()
        return incident, []

    def attach_media(
        self,
        incident_id: int,
        resident: User,
        files: list[FileStorage],
    ) -> tuple[bool, list[str]]:
        """Append evidence images to an incident (resident must own it)."""
        incident = self.incident_repo.get_by_id(incident_id)
        if incident is None:
            return False, ["Incident not found."]
        if incident.reported_by_id != resident.id:
            return False, ["You do not have permission to add media to this incident."]
        file_list = [f for f in files if f and f.filename]
        if not file_list:
            return False, ["No files provided."]
        created_media, errors = save_incident_media(incident, file_list)
        if not created_media and errors:
            return False, errors
        if not created_media:
            return False, ["No valid images could be saved."]
        self.update_repo.add(
            IncidentUpdate(
                incident_id=incident.id,
                updated_by_id=resident.id,
                from_status=incident.status,
                to_status=incident.status,
                note="Evidence image(s) added",
            )
        )
        db.session.commit()
        return True, []

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
            IncidentStatus.REJECTED,
        }:
            return True
        if current == IncidentStatus.IN_PROGRESS and target in {
            IncidentStatus.RESOLVED,
            IncidentStatus.REJECTED,
        }:
            return True
        return False


incident_service = IncidentService()
