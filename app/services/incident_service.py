from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, text

from app.constants import IncidentEventType, IncidentStatus, LocationMode
from app.extensions import db
from app.models import (
    DepartmentActionLog,
    Incident,
    IncidentAssignment,
    IncidentCategory,
    IncidentDispatch,
    Location,
)
from app.models.incident_update import IncidentUpdate
from app.models.user import User
from app.repositories.incident_event_repo import IncidentEventRepository
from app.repositories.incident_ownership_repo import IncidentOwnershipRepository
from app.repositories.incident_repo import IncidentRepository
from app.repositories.incident_update_repo import IncidentUpdateRepository
from app.services.incident_presets import get_preset, urgency_to_severity
from app.services.location_service import GeocodedLocation, location_service
from app.services.notification_service import notification_service
from app.services.routing_service import routing_service
from app.services.screening_service import screening_service
from app.utils.uploads import save_incident_media

if TYPE_CHECKING:
    from werkzeug.datastructures import FileStorage


@dataclass
class TimelineEvent:
    """Unified timeline event for incident history display."""

    at: datetime
    kind: str  # incident_created | status_update | dispatched | acknowledged | department_action
    title: str
    description: str
    actor_label: str
    metadata: dict[str, Any]


def _generate_reference_code(session, reported_at: datetime) -> str:
    """Generate a unique reference code using the DB sequence (same transaction as incident)."""
    bind = session.get_bind()
    if getattr(bind, "dialect", None) and bind.dialect.name == "postgresql":
        result = session.execute(text("SELECT nextval('incident_ref_seq')"))
        seq = result.scalar()
    else:
        # SQLite / other (e.g. tests): no sequence; use monotonic counter for uniqueness
        _generate_reference_code._sqlite_counter = (
            getattr(_generate_reference_code, "_sqlite_counter", 0) + 1
        )
        seq = _generate_reference_code._sqlite_counter % 1_000_000 or 1
    return f"HK-{reported_at.year:04d}-{reported_at.month:02d}-{seq:06d}"


class IncidentService:
    """Business logic for the incident lifecycle."""

    def __init__(
        self,
        incident_repo: IncidentRepository | None = None,
        update_repo: IncidentUpdateRepository | None = None,
        event_repo: IncidentEventRepository | None = None,
        ownership_repo: IncidentOwnershipRepository | None = None,
    ) -> None:
        self.incident_repo = incident_repo or IncidentRepository()
        self.update_repo = update_repo or IncidentUpdateRepository()
        self.event_repo = event_repo or IncidentEventRepository()
        self.ownership_repo = ownership_repo or IncidentOwnershipRepository()

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
        reference_code = _generate_reference_code(db.session, reported_at)

        # Optional structured / validated location enrichment via location_service.
        geocoded: GeocodedLocation | None = None
        freeform_address = location.strip(", ")
        if freeform_address and location_service.is_configured():
            geocoded = location_service.geocode(freeform_address)

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
            latitude=geocoded.latitude if geocoded is not None else latitude,
            longitude=geocoded.longitude if geocoded is not None else longitude,
            severity=severity,
            status=IncidentStatus.REPORTED.value,
            reported_at=reported_at,
            validated_address=geocoded.validated_address if geocoded is not None else None,
            suburb=geocoded.suburb if geocoded is not None else None,
            ward=geocoded.ward if geocoded is not None else None,
            location_validated=geocoded is not None,
            reference_code=reference_code,
            location_mode=location_mode,
            is_happening_now=is_happening_now_value,
            is_anyone_in_danger=is_anyone_in_danger_value,
            is_issue_still_present=is_issue_still_present_value,
            urgency_level=urgency_level or None,
        )

        self.incident_repo.add(incident)
        db.session.flush()
        # Run screening to capture system interpretation of the report.
        screening_result = screening_service.screen_incident(
            title=title,
            description=description,
            resident_category=category_obj,
        )
        incident.resident_category_id = category_obj.id if category_obj else None
        incident.system_category_id = (
            screening_result.system_category.id if screening_result.system_category else None
        )
        incident.suggested_authority_id = (
            screening_result.suggested_authority.id
            if screening_result.suggested_authority
            else None
        )
        if screening_result.suggested_priority and not incident.severity:
            incident.severity = screening_result.suggested_priority
        incident.suggested_priority = screening_result.suggested_priority
        incident.screening_confidence = screening_result.confidence
        incident.requires_admin_review = (
            screening_result.confidence < 0.7
            or "multi_department_candidate" in screening_result.flags
        )
        if screening_result.flags:
            incident.screening_notes = ", ".join(screening_result.flags)

        self.event_repo.create(
            incident_id=incident.id,
            event_type=IncidentEventType.INCIDENT_CREATED.value,
            from_status=None,
            to_status=IncidentStatus.REPORTED.value,
            actor_user_id=resident_user.id,
            actor_role="resident",
            note="Incident created",
        )

        created_update = IncidentUpdate(
            incident=incident,
            updated_by_id=resident_user.id,
            from_status=None,
            to_status=IncidentStatus.REPORTED.value,
            note="Incident created",
        )
        self.update_repo.add(created_update)

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
            routing_update = IncidentUpdate(
                incident=incident,
                updated_by_id=resident_user.id,
                from_status=IncidentStatus.REPORTED.value,
                to_status=IncidentStatus.REPORTED.value,
                note=f"Incident auto-routed to {routing_decision.authority.name}",
            )
            self.update_repo.add(routing_update)

        # Record screening decision in history for later analytics.
        if screening_result is not None:
            details = []
            if screening_result.system_category is not None:
                details.append(f"system_category={screening_result.system_category.name}")
            if screening_result.suggested_priority:
                details.append(f"suggested_priority={screening_result.suggested_priority}")
            details.append(f"confidence={screening_result.confidence:.2f}")
            if screening_result.flags:
                details.append(f"flags={','.join(screening_result.flags)}")
            screening_note = "Screened incident: " + "; ".join(details)
            screening_update = IncidentUpdate(
                incident=incident,
                updated_by_id=resident_user.id,
                from_status=IncidentStatus.REPORTED.value,
                to_status=IncidentStatus.REPORTED.value,
                note=screening_note,
            )
            self.update_repo.add(screening_update)

        db.session.flush()

        if routing_decision is not None and incident.id is not None:
            assignment = IncidentAssignment(
                incident_id=incident.id,
                authority_id=routing_decision.authority.id,
                assigned_by_user_id=resident_user.id,
                assigned_at=reported_at,
            )
            db.session.add(assignment)
            db.session.flush()
            dispatch = IncidentDispatch(
                incident_assignment_id=assignment.id,
                incident_id=incident.id,
                authority_id=routing_decision.authority.id,
                dispatch_method="internal_queue",
                dispatched_by_type="system",
                dispatched_by_id=None,
                destination_reference=None,
                delivery_status="pending",
                ack_status="pending",
                dispatched_at=reported_at,
            )
            db.session.add(dispatch)

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
                from_status=IncidentStatus.REPORTED.value,
                to_status=IncidentStatus.REPORTED.value,
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

    def assemble_timeline(self, incident_id: int) -> list[TimelineEvent]:
        """Build a unified timeline from IncidentUpdate, IncidentDispatch, DepartmentActionLog."""
        incident = self.incident_repo.get_by_id(incident_id)
        if incident is None:
            return []

        events: list[TimelineEvent] = []

        # Synthetic incident_created
        created_at = incident.reported_at or incident.created_at
        if created_at:
            events.append(
                TimelineEvent(
                    at=created_at,
                    kind="incident_created",
                    title="Incident reported",
                    description="Incident was created and submitted.",
                    actor_label=incident.reporter.name if incident.reporter else "Resident",
                    metadata={},
                )
            )

        # IncidentUpdate -> status_update (or general note)
        updates = list(self.update_repo.list_for_incident(incident_id))
        for u in updates:
            at = u.created_at
            if not at:
                continue
            # Skip the creation update; we already have synthetic incident_created
            if (
                u.from_status is None
                and u.to_status == IncidentStatus.REPORTED.value
                and (u.note or "").strip() == "Incident created"
            ):
                continue
            from_s = u.from_status or ""
            to_s = u.to_status or ""
            if from_s and from_s != to_s:
                title = (
                    f"Status: {from_s.replace('_', ' ').title()} → {to_s.replace('_', ' ').title()}"
                )
            elif to_s:
                title = to_s.replace("_", " ").title()
            else:
                title = "Update"
            actor = u.updater.name if u.updater else "System"
            events.append(
                TimelineEvent(
                    at=at,
                    kind="status_update",
                    title=title,
                    description=u.note or "",
                    actor_label=actor,
                    metadata={"from_status": from_s, "to_status": to_s},
                )
            )

        # IncidentDispatch -> dispatched, acknowledged
        dispatches = (
            (
                db.session.execute(
                    select(IncidentDispatch)
                    .where(IncidentDispatch.incident_id == incident_id)
                    .order_by(IncidentDispatch.dispatched_at.asc())
                )
            )
            .scalars()
            .all()
        )
        for d in dispatches:
            if d.dispatched_at:
                auth_name = d.authority.name if d.authority else "Department"
                events.append(
                    TimelineEvent(
                        at=d.dispatched_at,
                        kind="dispatched",
                        title=f"Dispatched to {auth_name}",
                        description=f"Via {d.dispatch_method or 'internal_queue'}",
                        actor_label=d.dispatcher.name if d.dispatcher else d.dispatched_by_type,
                        metadata={"authority_id": d.authority_id},
                    )
                )
            if d.ack_at and d.ack_status == "acknowledged":
                events.append(
                    TimelineEvent(
                        at=d.ack_at,
                        kind="acknowledged",
                        title="Department acknowledged",
                        description="Department has acknowledged the incident.",
                        actor_label=d.ack_user.name if d.ack_user else "Department",
                        metadata={},
                    )
                )

        # DepartmentActionLog -> department_action
        action_logs = (
            (
                db.session.execute(
                    select(DepartmentActionLog)
                    .where(DepartmentActionLog.incident_id == incident_id)
                    .order_by(DepartmentActionLog.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        for a in action_logs:
            if a.created_at:
                actor = a.performed_by.name if a.performed_by else "Department"
                events.append(
                    TimelineEvent(
                        at=a.created_at,
                        kind="department_action",
                        title=a.action_type.replace("_", " ").title(),
                        description=a.note or "",
                        actor_label=actor,
                        metadata={"action_type": a.action_type},
                    )
                )

        events.sort(key=lambda e: e.at)
        return events

    def list_incidents_for_resident(
        self,
        user: User,
        status: IncidentStatus | None = None,
    ) -> Iterable[Incident]:
        return self.incident_repo.list_for_resident(user.id, status=status)

    def search_incidents_for_resident(
        self,
        user: User,
        *,
        status: IncidentStatus | None = None,
        category_id: int | None = None,
        q: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        area: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ):
        """Wrapper around repository search for resident-facing explorer."""
        return self.incident_repo.search_for_resident(
            resident_id=user.id,
            status=status,
            category_id=category_id,
            q=q,
            date_from=date_from,
            date_to=date_to,
            area=area,
            page=page,
            per_page=per_page,
        )

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
            incident.reported_by_id == user.id and incident.status == IncidentStatus.REPORTED.value
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
        if incident.status != IncidentStatus.REPORTED.value:
            errors.append("Only reported incidents can be edited.")
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
        """Update incident status via canonical change_status path."""
        incident = self.incident_repo.get_by_id(incident_id)
        if incident is None:
            return False, ["Incident not found."]

        ok, errors = self.change_status(
            incident,
            to_status,
            actor_user_id=authority_user.id,
            actor_role=self._actor_role_from_user(authority_user),
            note=note.strip() or None,
            authority_id=incident.current_authority_id,
            allow_admin_override=allow_admin_override,
        )
        if not ok:
            return False, errors
        db.session.commit()
        return True, []

    def log_department_action(
        self,
        incident_id: int,
        authority_id: int,
        performed_by: User,
        action_type: str,
        note: str | None = None,
    ) -> DepartmentActionLog | None:
        """Log a department action on an incident. Creates and commits the log entry."""
        incident = self.incident_repo.get_by_id(incident_id)
        if incident is None:
            return None
        log = DepartmentActionLog(
            incident_id=incident_id,
            authority_id=authority_id,
            performed_by_id=performed_by.id,
            action_type=action_type,
            note=note,
        )
        db.session.add(log)
        db.session.commit()
        return log

    def change_status(
        self,
        incident: Incident,
        to_status: IncidentStatus,
        *,
        actor_user_id: int | None = None,
        actor_role: str,
        reason: str | None = None,
        note: str | None = None,
        authority_id: int | None = None,
        dispatch_id: int | None = None,
        allow_admin_override: bool = False,
    ) -> tuple[bool, list[str]]:
        """Canonical path for status changes. Validates, updates, writes events, updates ownership."""
        errors: list[str] = []
        try:
            current_status = IncidentStatus(incident.status)
        except ValueError:
            current_status = IncidentStatus.REPORTED

        if current_status == to_status:
            errors.append("Incident is already in that status.")
            return False, errors

        if not allow_admin_override and not self._is_valid_transition(current_status, to_status):
            errors.append("Invalid status transition.")
            return False, errors

        from_status = incident.status
        now = datetime.now(UTC)

        incident.status = to_status.value
        incident.version += 1
        if to_status == IncidentStatus.ASSIGNED and incident.assigned_at is None:
            incident.assigned_at = now
        if to_status == IncidentStatus.ACKNOWLEDGED and incident.acknowledged_at is None:
            incident.acknowledged_at = now
        if to_status == IncidentStatus.RESOLVED:
            incident.resolved_at = now
        if to_status == IncidentStatus.CLOSED:
            incident.closed_at = now

        event_type = self._event_type_for_transition(from_status, to_status)
        self.event_repo.create(
            incident_id=incident.id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status.value,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            authority_id=authority_id or incident.current_authority_id,
            dispatch_id=dispatch_id,
            reason=reason,
            note=note,
        )

        if current_status == IncidentStatus.SCREENED and to_status == IncidentStatus.ASSIGNED:
            if authority_id:
                self.ownership_repo.start_ownership(
                    incident.id,
                    authority_id,
                    assigned_by_user_id=actor_user_id,
                    dispatch_id=dispatch_id,
                    reason=reason,
                )
        elif to_status in (
            IncidentStatus.RESOLVED,
            IncidentStatus.CLOSED,
            IncidentStatus.REJECTED,
        ):
            self.ownership_repo.close_current(incident.id, ended_at=now)

        self.update_repo.add(
            IncidentUpdate(
                incident_id=incident.id,
                updated_by_id=actor_user_id,
                from_status=from_status,
                to_status=to_status.value,
                note=note or f"Status changed to {to_status.value}",
            )
        )

        notification_service.enqueue_status_changed(
            incident=incident,
            resident=incident.reporter,
        )

        return True, []

    def _event_type_for_transition(self, from_status: str, to_status: IncidentStatus) -> str:
        """Map transition to event type."""
        if to_status == IncidentStatus.REJECTED:
            return IncidentEventType.INCIDENT_REJECTED.value
        if to_status == IncidentStatus.CLOSED:
            return IncidentEventType.INCIDENT_CLOSED.value
        if to_status == IncidentStatus.RESOLVED:
            return IncidentEventType.INCIDENT_RESOLVED.value
        if to_status == IncidentStatus.ACKNOWLEDGED:
            return IncidentEventType.INCIDENT_ACKNOWLEDGED.value
        if to_status == IncidentStatus.ASSIGNED:
            return IncidentEventType.INCIDENT_ASSIGNED.value
        if to_status == IncidentStatus.SCREENED:
            return IncidentEventType.INCIDENT_SCREENED.value
        return IncidentEventType.STATUS_CHANGED.value

    @staticmethod
    def _actor_role_from_user(user: User) -> str:
        """Map user role to actor_role for events."""
        role = getattr(user, "role", None) or ""
        if role == "authority":
            return "department"
        if role in ("admin", "resident"):
            return role
        return "admin"

    @staticmethod
    def _is_valid_transition(
        current: IncidentStatus,
        target: IncidentStatus,
    ) -> bool:
        if current == IncidentStatus.REPORTED:
            return target in {IncidentStatus.SCREENED, IncidentStatus.REJECTED}
        if current == IncidentStatus.SCREENED:
            return target in {IncidentStatus.ASSIGNED, IncidentStatus.REJECTED}
        if current == IncidentStatus.ASSIGNED:
            return target in {
                IncidentStatus.ACKNOWLEDGED,
                IncidentStatus.IN_PROGRESS,
                IncidentStatus.REJECTED,
            }
        if current == IncidentStatus.ACKNOWLEDGED:
            return target in {IncidentStatus.IN_PROGRESS, IncidentStatus.REJECTED}
        if current == IncidentStatus.IN_PROGRESS:
            return target in {IncidentStatus.RESOLVED, IncidentStatus.REJECTED}
        if current == IncidentStatus.RESOLVED:
            return target == IncidentStatus.CLOSED
        return False


incident_service = IncidentService()
