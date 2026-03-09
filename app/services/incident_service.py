from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.constants import IncidentStatus, LocationMode
from app.extensions import db
from app.models import (
    Incident,
    IncidentAssignment,
    IncidentCategory,
    Location,
)
from app.models.incident_update import IncidentUpdate
from app.models.user import User
from app.repositories.incident_repo import IncidentRepository
from app.repositories.incident_update_repo import IncidentUpdateRepository
from app.services.incident_presets import get_preset, urgency_to_severity
from app.services.notification_service import notification_service
from app.services.routing_service import routing_service
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
        urgency_level = (payload.get("urgency_level") or "").strip() or None
        location_mode = (payload.get("location_mode") or "").strip() or None
        # Raw guided booleans from the form; unchecked checkboxes are missing from payload
        is_happening_now = payload.get("is_happening_now") in (True, "1", "on", "yes", "true")
        is_anyone_in_danger = payload.get("is_anyone_in_danger") in (
            True,
            "1",
            "on",
            "yes",
            "true",
        )
        is_issue_still_present = payload.get("is_issue_still_present") in (
            True,
            "1",
            "on",
            "yes",
            "true",
        )

        # Optional structured fields
        category_id_raw = payload.get("category_id")
        location_id_raw = payload.get("location_id")
        latitude_raw = payload.get("latitude")
        longitude_raw = payload.get("longitude")

        category_obj: IncidentCategory | None = None
        location_obj: Location | None = None
        latitude = None
        longitude = None

        if category_id_raw:
            try:
                category_obj = db.session.get(
                    IncidentCategory,
                    int(category_id_raw),
                )
                if category_obj is None:
                    errors.append("Invalid category selected.")
                elif not getattr(category_obj, "is_active", True):
                    errors.append("Selected category is not available.")
                    category_obj = None
            except (TypeError, ValueError):
                errors.append("Invalid category selected.")
                category_obj = None

        # Apply presets: suggested title and default urgency when category is known
        preset = get_preset(category_obj) if category_obj else None
        if category_obj is not None and preset:
            if not title:
                title = preset.get("suggested_title") or "Incident reported"
            if not severity and not urgency_level:
                urgency_level = getattr(
                    preset.get("default_urgency"),
                    "value",
                    preset.get("default_urgency"),
                )
            if not severity:
                severity = urgency_to_severity(urgency_level)
        if urgency_level and not severity:
            severity = urgency_to_severity(urgency_level)

        if not title:
            errors.append("Title is required.")
        if not description:
            errors.append("Description is required.")
        if not category and not category_obj:
            errors.append("Category is required.")
        if category_obj is not None:
            category = category_obj.name

        # When location_mode is saved, fill from resident profile if fields are empty
        if location_mode == LocationMode.SAVED.value:
            profile = getattr(resident_user, "resident_profile", None)
            if profile:
                if not suburb_or_ward:
                    suburb_or_ward = (getattr(profile, "suburb", None) or "").strip()
                if not street_or_landmark:
                    street_or_landmark = (getattr(profile, "street_address_1", None) or "").strip()

        if not suburb_or_ward:
            errors.append("Suburb/ward is required.")
        if not street_or_landmark:
            errors.append("Street/landmark is required.")
        if not severity:
            errors.append("Severity is required.")

        if location_id_raw:
            try:
                location_obj = db.session.get(Location, int(location_id_raw))
                if location_obj is None:
                    errors.append("Invalid location selected.")
            except (TypeError, ValueError):
                errors.append("Invalid location selected.")
                location_obj = None

        if latitude_raw and longitude_raw:
            try:
                latitude = float(latitude_raw)
                longitude = float(longitude_raw)
                if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                    errors.append("Latitude must be -90 to 90 and longitude -180 to 180.")
                    latitude = longitude = None
            except (TypeError, ValueError):
                latitude = None
                longitude = None

        if location_mode and location_mode not in (
            LocationMode.SAVED.value,
            LocationMode.CURRENT.value,
            LocationMode.OTHER.value,
        ):
            location_mode = None

        if errors:
            return None, errors

        if category_obj is not None:
            category = category_obj.name

        # Decide how to store guided boolean fields:
        # - If the preset marks a question as applicable (ask_is_* = True), persist
        #   True or False explicitly so we can distinguish "asked but answered no".
        # - If the question does not apply (ask_is_* = False) and no preset exists,
        #   keep the DB value as None ("not asked").
        ask_is_happening_now = False
        ask_is_anyone_in_danger = False
        ask_is_issue_still_present = False
        if preset:
            ask_is_happening_now = bool(preset.get("ask_is_happening_now", False))
            ask_is_anyone_in_danger = bool(preset.get("ask_is_anyone_in_danger", False))
            ask_is_issue_still_present = bool(preset.get("ask_is_issue_still_present", False))
        else:
            # For non-preset flows, treat presence of the field as "question was asked".
            ask_is_happening_now = "is_happening_now" in payload
            ask_is_anyone_in_danger = "is_anyone_in_danger" in payload
            ask_is_issue_still_present = "is_issue_still_present" in payload

        is_happening_now_value: bool | None = None
        is_anyone_in_danger_value: bool | None = None
        is_issue_still_present_value: bool | None = None
        if ask_is_happening_now:
            # Checkbox checked -> True, unchecked (missing) -> False
            is_happening_now_value = is_happening_now
        if ask_is_anyone_in_danger:
            is_anyone_in_danger_value = is_anyone_in_danger
        if ask_is_issue_still_present:
            is_issue_still_present_value = is_issue_still_present

        location = f"{street_or_landmark}, {suburb_or_ward}"
        reported_at = datetime.now(UTC)

        incident = Incident(
            reported_by_id=resident_user.id,
            resident_profile_id=getattr(
                getattr(resident_user, "resident_profile", None),
                "id",
                None,
            ),
            title=title,
            description=description,
            category=category,
            category_id=category_obj.id if category_obj else None,
            suburb_or_ward=suburb_or_ward,
            street_or_landmark=street_or_landmark,
            nearest_place=nearest_place,
            location=location,
            location_id=location_obj.id if location_obj else None,
            latitude=latitude,
            longitude=longitude,
            severity=severity,
            status=IncidentStatus.PENDING.value,
            reported_at=reported_at,
            location_mode=location_mode,
            is_happening_now=is_happening_now_value,
            is_anyone_in_danger=is_anyone_in_danger_value,
            is_issue_still_present=is_issue_still_present_value,
            urgency_level=urgency_level or None,
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

        # Resolve routing based on category and location if possible (best-effort).
        routing_decision = None
        if category_obj is not None:
            routing_decision = routing_service.resolve(
                category=category_obj,
                location=location_obj,
            )
            if routing_decision is not None:
                incident.current_authority_id = routing_decision.authority.id
                incident.assigned_at = reported_at
                if not severity and routing_decision.priority:
                    incident.severity = routing_decision.priority

        db.session.flush()

        if routing_decision is not None and incident.id is not None:
            db.session.add(
                IncidentAssignment(
                    incident_id=incident.id,
                    authority_id=routing_decision.authority.id,
                    assigned_by_user_id=resident_user.id,
                    assigned_at=reported_at,
                )
            )

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
        *,
        allow_admin_override: bool = False,
    ) -> tuple[bool, list[str]]:
        errors: list[str] = []
        incident = self.incident_repo.get_by_id(incident_id)
        if incident is None:
            errors.append("Incident not found.")
            return False, errors

        try:
            current_status = IncidentStatus(incident.status)
        except ValueError:
            current_status = IncidentStatus.PENDING

        if current_status == to_status:
            errors.append("Incident is already in that status.")
            return False, errors

        if not allow_admin_override and not self._is_valid_transition(current_status, to_status):
            errors.append("Invalid status transition.")
            return False, errors

        from_status = incident.status
        incident.status = to_status.value
        incident.version += 1

        now = datetime.now(UTC)
        if incident.acknowledged_at is None and current_status == IncidentStatus.PENDING:
            incident.acknowledged_at = now
        if to_status == IncidentStatus.ASSIGNED and incident.assigned_at is None:
            incident.assigned_at = now
        if to_status == IncidentStatus.RESOLVED:
            incident.resolved_at = now
        if to_status == IncidentStatus.CLOSED:
            incident.closed_at = now

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
        # reported (PENDING) -> verified or rejected only; no direct to resolved unless admin
        if current == IncidentStatus.PENDING:
            return target in {
                IncidentStatus.VERIFIED,
                IncidentStatus.REJECTED,
            }
        if current == IncidentStatus.VERIFIED:
            return target in {
                IncidentStatus.ASSIGNED,
                IncidentStatus.REJECTED,
            }
        if current == IncidentStatus.ASSIGNED:
            return target in {
                IncidentStatus.IN_PROGRESS,
                IncidentStatus.REJECTED,
            }
        if current == IncidentStatus.IN_PROGRESS:
            return target in {
                IncidentStatus.RESOLVED,
                IncidentStatus.REJECTED,
            }
        if current == IncidentStatus.RESOLVED:
            return target == IncidentStatus.CLOSED
        return False


incident_service = IncidentService()
