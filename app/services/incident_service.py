from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, text

from app.constants import IncidentEventType, IncidentStatus, LocationMode
from app.extensions import db
from app.models import (
    Authority,
    DepartmentActionLog,
    Incident,
    IncidentAssignment,
    IncidentCategory,
    IncidentDispatch,
    IncidentEvent,
    IncidentSlaTracking,
    Location,
)
from app.models.incident_update import IncidentUpdate
from app.models.user import User
from app.repositories.incident_event_repo import IncidentEventRepository
from app.repositories.incident_ownership_repo import IncidentOwnershipRepository
from app.repositories.incident_repo import IncidentRepository
from app.repositories.incident_update_repo import IncidentUpdateRepository
from app.services.audit_service import audit_service
from app.services.incident_dynamic_schema import (
    build_generated_description,
    get_category_schema,
    validate_details,
)
from app.services.incident_presets import get_preset, urgency_to_severity
from app.services.location_service import GeocodedLocation, location_service
from app.services.notification_service import notification_service
from app.services.routing_service import routing_service
from app.services.screening_service import screening_service
from app.utils.datetime_helpers import utc_now
from app.utils.uploads import save_incident_media

if TYPE_CHECKING:
    from werkzeug.datastructures import FileStorage


@dataclass
class TimelineEvent:
    """Unified timeline event for incident history display."""

    at: datetime
    kind: str  # incident_created | status_update | dispatched | acknowledged | department_action | evidence_uploaded
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

    @staticmethod
    def _normalize_category_token(value: str | None) -> str:
        if not value:
            return ""
        return value.strip().lower().replace("-", "_").replace(" ", "_")

    def _resolve_routing_category(self, incident: Incident) -> IncidentCategory | None:
        """Resolve best category for routing lookups using IDs first, then normalized text fallback."""
        for category_id in (
            getattr(incident, "final_category_id", None),
            getattr(incident, "reported_category_id", None),
            getattr(incident, "system_category_id", None),
            getattr(incident, "resident_category_id", None),
            getattr(incident, "category_id", None),
        ):
            if category_id:
                category = db.session.get(IncidentCategory, category_id)
                if category is not None and getattr(category, "is_active", True):
                    return category

        token = self._normalize_category_token(getattr(incident, "category", None))
        if not token:
            return None
        categories = (
            db.session.query(IncidentCategory).filter(IncidentCategory.is_active.is_(True)).all()
        )
        for category in categories:
            if self._normalize_category_token(category.name) == token:
                return category
        return None

    def _backfill_suggested_authority(self, incident: Incident) -> None:
        """Populate suggested_authority_id from routing rules when screening suggestion is missing."""
        decision = routing_service.resolve_best_route(incident)
        routing_service.apply_route_suggestion(incident, decision)

    @staticmethod
    def _resolve_sla_hours_for_incident(incident: Incident) -> int:
        if (
            incident.category_rel is not None
            and incident.category_rel.default_sla_hours is not None
        ):
            return int(incident.category_rel.default_sla_hours)
        if incident.category_id:
            category = db.session.get(IncidentCategory, incident.category_id)
            if category is not None and category.default_sla_hours is not None:
                return int(category.default_sla_hours)
        return 72

    @staticmethod
    def _to_naive_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    def _upsert_sla_tracking(self, incident: Incident) -> IncidentSlaTracking:
        now = self._to_naive_utc(utc_now())
        started_at = (
            self._to_naive_utc(incident.reported_at)
            or self._to_naive_utc(incident.created_at)
            or now
        )
        sla_hours = self._resolve_sla_hours_for_incident(incident)
        deadline_at = started_at + timedelta(hours=sla_hours)
        tracking = db.session.execute(
            select(IncidentSlaTracking).where(IncidentSlaTracking.incident_id == incident.id)
        ).scalar_one_or_none()
        if tracking is None:
            tracking = IncidentSlaTracking(
                incident_id=incident.id,
                status="open",
                sla_hours=sla_hours,
                deadline_at=deadline_at,
            )
            db.session.add(tracking)
        else:
            tracking.sla_hours = sla_hours
            tracking.deadline_at = deadline_at
            if tracking.status != "closed":
                tracking.status = "open"
                tracking.closed_at = None
        deadline_at = self._to_naive_utc(tracking.deadline_at)
        if deadline_at is not None and deadline_at <= now and tracking.status != "closed":
            tracking.status = "breached"
            tracking.breached_at = tracking.breached_at or now
        return tracking

    def _close_sla_tracking_if_needed(self, incident: Incident) -> None:
        tracking = db.session.execute(
            select(IncidentSlaTracking).where(IncidentSlaTracking.incident_id == incident.id)
        ).scalar_one_or_none()
        if tracking is None:
            return
        if tracking.status != "closed":
            tracking.status = "closed"
            tracking.closed_at = utc_now()

    def _refresh_sla_breach_state(self, incident: Incident) -> None:
        tracking = db.session.execute(
            select(IncidentSlaTracking).where(IncidentSlaTracking.incident_id == incident.id)
        ).scalar_one_or_none()
        if tracking is None or tracking.status == "closed":
            return
        now = self._to_naive_utc(utc_now())
        deadline_at = self._to_naive_utc(tracking.deadline_at)
        if deadline_at is not None and deadline_at <= now:
            tracking.status = "breached"
            tracking.breached_at = tracking.breached_at or now
        elif tracking.status == "breached":
            tracking.status = "open"

    def create_incident(
        self,
        payload: dict,
        resident_user: User,
        files: list[FileStorage] | None = None,
    ) -> tuple[Incident | None, list[str]]:
        errors: list[str] = []

        title = (payload.get("title") or "").strip()
        description = (payload.get("description") or "").strip()
        additional_notes = (payload.get("additional_notes") or "").strip() or None
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
        if not category and not category_obj:
            errors.append("Category is required.")
        if category_obj is not None:
            category = category_obj.name
        category_schema = get_category_schema(category)
        raw_dynamic_details = payload.get("dynamic_details") or {}
        dynamic_details = raw_dynamic_details if isinstance(raw_dynamic_details, dict) else {}
        errors.extend(validate_details(category_schema, dynamic_details))
        generated_description = build_generated_description(
            category_schema,
            dynamic_details,
            additional_notes,
        )
        user_edited_description = bool(payload.get("description_manually_edited"))
        if not description or not user_edited_description:
            description = generated_description
        if not description:
            errors.append("Description is required.")

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
        reported_at = utc_now()
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
            additional_notes=additional_notes,
            dynamic_details=dynamic_details or None,
            category=category,
            category_id=category_obj.id if category_obj else None,
            reported_category_id=category_obj.id if category_obj else None,
            suburb_or_ward=suburb_or_ward,
            street_or_landmark=street_or_landmark,
            nearest_place=nearest_place,
            location=location,
            location_id=location_obj.id if location_obj else None,
            latitude=geocoded.latitude if geocoded is not None else latitude,
            longitude=geocoded.longitude if geocoded is not None else longitude,
            location_precision=(
                "exact"
                if geocoded is not None
                else ("approximate" if latitude is not None and longitude is not None else None)
            ),
            geocoded_at=utc_now() if geocoded is not None else None,
            geocode_source="google_maps" if geocoded is not None else None,
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
        incident.final_category_id = (
            screening_result.system_category.id
            if screening_result.system_category
            else (category_obj.id if category_obj else None)
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

        # Phase-A routing: suggest best authority only (no auto assignment/dispatch yet).
        decision = routing_service.resolve_best_route(incident)
        routing_service.apply_route_suggestion(incident, decision)

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

        # Phase B1: auto-apply high-confidence, exact-location routing (assignment + ownership only).
        #
        # Guardrails:
        # - only when routing is "high" confidence
        # - only when there is an exact `location_id` match
        # - only when incident is not flagged for admin review
        # - only when no current authority/ownership exists
        if (
            decision.authority_id is not None
            and decision.confidence == "high"
            and incident.location_id is not None
            and decision.matched_location_id == incident.location_id
            and incident.requires_admin_review is False
            and incident.current_authority_id is None
            and incident.duplicate_of_incident_id is None
        ):
            current_ownership = self.ownership_repo.get_current(incident.id)
            if current_ownership is None:
                existing_assignment = (
                    db.session.execute(
                        select(IncidentAssignment).where(
                            IncidentAssignment.incident_id == incident.id,
                            IncidentAssignment.authority_id == decision.authority_id,
                        )
                    )
                    .scalars()
                    .first()
                )
                if existing_assignment is None:
                    existing_assignment = IncidentAssignment(
                        incident_id=incident.id,
                        authority_id=decision.authority_id,
                        assigned_to_user_id=None,
                        assigned_by_user_id=None,
                        assignment_reason="Auto-assigned after high-confidence routing (phase B1).",
                        assigned_at=reported_at,
                    )
                    db.session.add(existing_assignment)
                    db.session.flush()

                incident.current_authority_id = decision.authority_id
                self.ownership_repo.start_ownership(
                    incident_id=incident.id,
                    authority_id=decision.authority_id,
                    assigned_by_user_id=None,
                    dispatch_id=None,
                    reason="Auto-assigned after high-confidence routing (phase B1).",
                )

                route_applied_event = IncidentEvent(
                    incident_id=incident.id,
                    event_type=IncidentEventType.ROUTE_APPLIED.value,
                    actor_user_id=None,
                    actor_role="system",
                    authority_id=decision.authority_id,
                    dispatch_id=None,
                    assignment_id=existing_assignment.id,
                    from_status=None,
                    to_status=None,
                    reason="Route applied (phase B1 auto-assignment).",
                    note=decision.reason,
                    metadata_json={
                        "routing_rule_id": decision.routing_rule_id,
                        "matched_location_id": decision.matched_location_id,
                        "matched_category_id": decision.matched_category_id,
                        "confidence": decision.confidence,
                        "priority": decision.priority,
                        "score": decision.score,
                    },
                )
                db.session.add(route_applied_event)
        self._upsert_sla_tracking(incident)
        db.session.commit()
        return incident, []

    def confirm_screening(
        self,
        incident_id: int,
        actor_user: User,
    ) -> tuple[bool, list[str]]:
        """Canonical screening confirmation: move to screened/assigned and create dispatch."""
        incident = self.incident_repo.get_by_id(incident_id)
        if incident is None:
            return False, ["Incident not found."]
        if not incident.suggested_authority_id:
            self._backfill_suggested_authority(incident)
        if not incident.suggested_authority_id:
            return False, ["No suggested department to confirm for this incident."]

        authority_id = incident.suggested_authority_id
        authority = db.session.get(Authority, authority_id)
        if authority is None or not authority.is_active:
            return False, ["Suggested department is no longer available."]
        incident.current_authority_id = authority_id
        incident.requires_admin_review = False
        incident.verification_status = "approved"
        incident.verified_at = utc_now()
        incident.verified_by_user_id = actor_user.id

        if incident.status in (
            IncidentStatus.REPORTED.value,
            IncidentStatus.AWAITING_EVIDENCE.value,
        ):
            ok, errors = self.change_status(
                incident,
                IncidentStatus.SCREENED,
                actor_user_id=actor_user.id,
                actor_role=self._actor_role_from_user(actor_user),
                note="Screening confirmed by admin",
                allow_admin_override=True,
            )
            if not ok:
                return False, errors

        # Phase B1 safety: if the incident was auto-assigned, reuse the existing assignment.
        assignment = (
            db.session.execute(
                select(IncidentAssignment)
                .where(
                    IncidentAssignment.incident_id == incident.id,
                    IncidentAssignment.authority_id == authority_id,
                )
                .order_by(IncidentAssignment.id.desc())
            )
            .scalars()
            .first()
        )
        if assignment is None:
            assignment = IncidentAssignment(
                incident_id=incident.id,
                authority_id=authority_id,
                assigned_by_user_id=actor_user.id,
            )
            db.session.add(assignment)
            db.session.flush()
        else:
            # If system created assignment without an assigning admin, annotate it now.
            if assignment.assigned_by_user_id is None:
                assignment.assigned_by_user_id = actor_user.id

        dispatch = (
            db.session.execute(
                select(IncidentDispatch)
                .where(IncidentDispatch.incident_assignment_id == assignment.id)
                .order_by(IncidentDispatch.id.desc())
            )
            .scalars()
            .first()
        )
        from app.services.dispatch_service import dispatch_service

        if dispatch is None:
            dispatch = IncidentDispatch(
                incident_assignment_id=assignment.id,
                incident_id=incident.id,
                authority_id=authority_id,
                dispatch_method="internal_queue",
                dispatched_by_type="admin",
                dispatched_by_id=actor_user.id,
                status="pending",
                delivery_status="pending",
                ack_status="pending",
                last_status_update_at=utc_now(),
            )
            db.session.add(dispatch)
            db.session.flush()
            dispatch_service.send_assignment_dispatch(dispatch)
        else:
            # Only send again if we haven't actually sent the dispatch before.
            if (dispatch.delivery_status or "").strip().lower() != "sent":
                dispatch_service.send_assignment_dispatch(dispatch)

        if incident.status == IncidentStatus.SCREENED.value:
            ok, errors = self.change_status(
                incident,
                IncidentStatus.ASSIGNED,
                actor_user_id=actor_user.id,
                actor_role=self._actor_role_from_user(actor_user),
                note="Incident assigned after screening confirmation",
                authority_id=authority_id,
                dispatch_id=dispatch.id,
            )
            if not ok:
                return False, errors

        db.session.commit()
        return True, []

    def review_proof(
        self,
        incident_id: int,
        *,
        actor_user: User,
        decision: str,
        note: str | None = None,
    ) -> tuple[bool, list[str]]:
        """Approve or reject proof as an explicit verification action."""
        incident = self.incident_repo.get_by_id(incident_id)
        if incident is None:
            return False, ["Incident not found."]
        decision_norm = (decision or "").strip().lower()
        note_norm = (note or "").strip() or None
        if decision_norm not in {"approved", "rejected"}:
            return False, ["Invalid proof decision."]

        incident.verification_notes = note_norm
        incident.verified_at = utc_now()
        incident.verified_by_user_id = actor_user.id

        if decision_norm == "approved":
            incident.verification_status = "approved"
            audit_service.log(
                entity_type="incident",
                entity_id=incident.id,
                action="proof_verified",
                actor_user_id=actor_user.id,
                actor_role=self._actor_role_from_user(actor_user),
                reason=note_norm,
                after_json={"verification_status": "approved"},
            )
            # Approve must advance workflow: verification alone left incidents stuck in awaiting_evidence.
            if incident.status == IncidentStatus.AWAITING_EVIDENCE.value:
                incident.proof_request_reason = None
                incident.proof_requested_at = None
                incident.proof_requested_by_user_id = None
                ok, errors = self.change_status(
                    incident,
                    IncidentStatus.REPORTED,
                    actor_user_id=actor_user.id,
                    actor_role=self._actor_role_from_user(actor_user),
                    note=note_norm or "Proof approved by admin; incident ready for screening.",
                    allow_admin_override=True,
                )
                if not ok:
                    return False, errors
            elif incident.status == IncidentStatus.REPORTED.value:
                # Proof OK while already reported — record visible timeline entry.
                self.update_repo.add(
                    IncidentUpdate(
                        incident_id=incident.id,
                        updated_by_id=actor_user.id,
                        from_status=incident.status,
                        to_status=incident.status,
                        note=note_norm or "Proof approved by admin",
                    )
                )
            db.session.commit()
            return True, []

        incident.verification_status = "rejected"
        audit_service.log(
            entity_type="incident",
            entity_id=incident.id,
            action="proof_rejected",
            actor_user_id=actor_user.id,
            actor_role=self._actor_role_from_user(actor_user),
            reason=note_norm,
            after_json={"verification_status": "rejected"},
        )
        ok, errors = self.change_status(
            incident,
            IncidentStatus.REJECTED,
            actor_user_id=actor_user.id,
            actor_role=self._actor_role_from_user(actor_user),
            reason=note_norm,
            note=note_norm or "Proof was rejected by admin review",
            allow_admin_override=True,
        )
        if not ok:
            return False, errors
        db.session.commit()
        return True, []

    def request_additional_proof(
        self,
        incident_id: int,
        *,
        actor_user: User,
        reason: str,
    ) -> tuple[bool, list[str]]:
        """Request more resident evidence and move incident to awaiting_evidence."""
        incident = self.incident_repo.get_by_id(incident_id)
        if incident is None:
            return False, ["Incident not found."]

        reason_norm = (reason or "").strip()
        if not reason_norm:
            return False, ["Reason is required when requesting additional proof."]
        if incident.status not in (IncidentStatus.REPORTED.value, IncidentStatus.SCREENED.value):
            return False, ["Additional proof can only be requested before assignment."]

        incident.verification_status = "needs_more_evidence"
        incident.proof_requested_at = utc_now()
        incident.proof_requested_by_user_id = actor_user.id
        incident.proof_request_reason = reason_norm
        incident.verification_notes = reason_norm
        audit_service.log(
            entity_type="incident",
            entity_id=incident.id,
            action="proof_requested",
            actor_user_id=actor_user.id,
            actor_role=self._actor_role_from_user(actor_user),
            reason=reason_norm,
            after_json={"verification_status": "needs_more_evidence"},
        )

        ok, errors = self.change_status(
            incident,
            IncidentStatus.AWAITING_EVIDENCE,
            actor_user_id=actor_user.id,
            actor_role=self._actor_role_from_user(actor_user),
            reason=reason_norm,
            note=f"Additional proof requested: {reason_norm}",
            allow_admin_override=True,
        )
        if not ok:
            return False, errors
        db.session.commit()
        return True, []

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
        """Build timeline from incident_events (primary), fallback to IncidentUpdate for legacy."""
        incident = self.incident_repo.get_by_id(incident_id)
        if incident is None:
            return []

        event_rows = self.event_repo.list_for_incident(incident_id)
        if event_rows:
            return self._timeline_from_events(incident, event_rows)
        return self._timeline_from_legacy(incident_id, incident)

    def _timeline_from_events(self, incident: Incident, event_rows: list) -> list[TimelineEvent]:
        """Build timeline from incident_events (read-first)."""
        events: list[TimelineEvent] = []
        for ev in event_rows:
            at = ev.created_at
            if not at:
                continue
            kind, title, desc = self._event_to_timeline(ev, incident)
            actor_label = ev.actor.name if ev.actor else (ev.actor_role or "System")
            events.append(
                TimelineEvent(
                    at=at,
                    kind=kind,
                    title=title,
                    description=desc or "",
                    actor_label=actor_label,
                    metadata={
                        "from_status": ev.from_status,
                        "to_status": ev.to_status,
                        "event_type": ev.event_type,
                    },
                )
            )
        events.extend(self._department_action_events(incident.id))
        events.sort(key=lambda e: e.at)
        return events

    def _event_to_timeline(self, ev, incident: Incident) -> tuple[str, str, str]:
        """Map IncidentEvent to (kind, title, description)."""
        f = ev.from_status or ""
        t = ev.to_status or ""
        note = ev.note or ""
        if ev.event_type == IncidentEventType.INCIDENT_CREATED.value:
            return (
                "incident_created",
                "Incident reported",
                note or "Incident was created and submitted.",
            )
        if ev.event_type == IncidentEventType.INCIDENT_ACKNOWLEDGED.value:
            auth = ev.authority.name if ev.authority else "Department"
            return (
                "acknowledged",
                "Department acknowledged",
                note or f"Acknowledged by {auth}.",
            )
        if ev.event_type == IncidentEventType.ROUTE_SUGGESTED.value:
            return (
                "route_suggested",
                "Route suggested",
                note or "Routing engine suggested a department.",
            )
        if ev.event_type == IncidentEventType.ROUTING_FAILED.value:
            return (
                "routing_failed",
                "Routing failed",
                note or "No routing rule matched; admin review required.",
            )
        if ev.event_type == IncidentEventType.ROUTE_APPLIED.value:
            auth = ev.authority.name if ev.authority else "Department"
            return (
                "route_applied",
                "Route applied",
                note or f"Auto-assigned to {auth}.",
            )
        if ev.event_type in (
            IncidentEventType.INCIDENT_ASSIGNED.value,
            IncidentEventType.DISPATCH_CREATED.value,
            IncidentEventType.DISPATCH_DELIVERED.value,
        ):
            auth = ev.authority.name if ev.authority else "Department"
            return ("dispatched", f"Dispatched to {auth}", note)
        if ev.event_type == IncidentEventType.EVIDENCE_UPLOADED.value:
            return ("evidence_uploaded", "Evidence uploaded", note)
        if ev.event_type == IncidentEventType.PROOF_REQUESTED.value:
            return (
                "proof_requested",
                "Additional proof requested",
                note or "Admin requested more evidence before escalation.",
            )
        if ev.event_type == IncidentEventType.AUTHORITY_PROGRESS_UPDATE.value:
            return (
                "authority_progress",
                "Authority progress update",
                note or "Authority provided a progress update.",
            )
        if ev.event_type == IncidentEventType.AUTHORITY_RESOLUTION_UPDATE.value:
            return (
                "authority_resolution",
                "Authority resolution update",
                note or "Authority marked work as resolved.",
            )
        if f and t and f != t:
            title = f"Status: {f.replace('_', ' ').title()} → {t.replace('_', ' ').title()}"
        elif t:
            title = t.replace("_", " ").title()
        else:
            title = "Update"
        return ("status_update", title, note)

    def _department_action_events(self, incident_id: int) -> list[TimelineEvent]:
        """DepartmentActionLog events (operational work proof)."""
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
        return [
            TimelineEvent(
                at=a.created_at,
                kind="department_action",
                title=a.action_type.replace("_", " ").title(),
                description=a.note or "",
                actor_label=a.performed_by.name if a.performed_by else "Department",
                metadata={"action_type": a.action_type},
            )
            for a in action_logs
            if a.created_at
        ]

    def _timeline_from_legacy(self, incident_id: int, incident: Incident) -> list[TimelineEvent]:
        """Fallback: build from IncidentUpdate, IncidentDispatch (legacy)."""
        events: list[TimelineEvent] = []
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
        updates = list(self.update_repo.list_for_incident(incident_id))
        for u in updates:
            if not u.created_at:
                continue
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
                    at=u.created_at,
                    kind="status_update",
                    title=title,
                    description=u.note or "",
                    actor_label=actor,
                    metadata={"from_status": from_s, "to_status": to_s},
                )
            )
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
            if d.sent_at:
                auth_name = d.authority.name if d.authority else "Department"
                dispatch_desc = f"Via {d.channel or 'internal_queue'}"
                if d.external_reference_number:
                    dispatch_desc += f" | External ref: {d.external_reference_number}"
                events.append(
                    TimelineEvent(
                        at=d.sent_at,
                        kind="dispatched",
                        title=f"Dispatched to {auth_name}",
                        description=dispatch_desc,
                        actor_label=d.dispatcher.name if d.dispatcher else d.dispatched_by_type,
                        metadata={"authority_id": d.authority_id},
                    )
                )
            if d.acknowledged_at and d.ack_status == "acknowledged":
                events.append(
                    TimelineEvent(
                        at=d.acknowledged_at,
                        kind="acknowledged",
                        title="Department acknowledged",
                        description="Department has acknowledged the incident.",
                        actor_label=d.ack_user.name if d.ack_user else "Department",
                        metadata={},
                    )
                )
        events.extend(self._department_action_events(incident_id))
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
        """True if the resident is the reporter and the incident may still be edited by them."""
        if incident.reported_by_id != user.id:
            return False
        return incident.status in (
            IncidentStatus.REPORTED.value,
            IncidentStatus.AWAITING_EVIDENCE.value,
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
        if incident.status not in (
            IncidentStatus.REPORTED.value,
            IncidentStatus.AWAITING_EVIDENCE.value,
        ):
            errors.append("This incident can no longer be edited.")
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
        normalized_status = str(getattr(incident, "status", "")).strip().lower()
        if normalized_status == IncidentStatus.AWAITING_EVIDENCE.value:
            if incident.status != IncidentStatus.AWAITING_EVIDENCE.value:
                # Canonicalize legacy/malformed status values before transition.
                incident.status = IncidentStatus.AWAITING_EVIDENCE.value
            incident.evidence_resubmitted_at = utc_now()
            incident.verification_status = "pending"
            # Close the proof-request loop: move back to reported and alert admins.
            ok, errors = self.change_status(
                incident,
                IncidentStatus.REPORTED,
                actor_user_id=resident.id,
                actor_role=self._actor_role_from_user(resident),
                note="Additional proof submitted by resident",
            )
            if not ok:
                db.session.rollback()
                return False, errors
            notification_service.enqueue_admins_proof_submitted(incident)
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
            reason=note.strip() or None,
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

    def create_dispatch(
        self,
        *,
        incident_id: int,
        authority_id: int,
        incident_assignment_id: int | None,
        channel: str = "email",
        recipient_email: str | None = None,
        subject_snapshot: str | None = None,
        message_snapshot: str | None = None,
        created_by_user_id: int | None = None,
        dispatched_by_type: str = "admin",
    ) -> IncidentDispatch:
        """Create a dispatch record with initial pending status."""
        now = utc_now()
        dispatch = IncidentDispatch(
            incident_id=incident_id,
            authority_id=authority_id,
            incident_assignment_id=incident_assignment_id,
            channel=channel,
            status="pending",
            recipient_email=recipient_email,
            subject_snapshot=subject_snapshot,
            message_snapshot=message_snapshot,
            created_by_user_id=created_by_user_id,
            dispatched_by_type=dispatched_by_type,
            sent_at=now,
            last_status_update_at=now,
            delivery_status="pending",
            ack_status="pending",
        )
        db.session.add(dispatch)
        db.session.flush()
        return dispatch

    def mark_sent(
        self,
        dispatch: IncidentDispatch,
        *,
        delivery_provider: str | None = None,
        delivery_reference: str | None = None,
    ) -> IncidentDispatch:
        now = utc_now()
        dispatch.status = "sent"
        dispatch.sent_at = dispatch.sent_at or now
        dispatch.delivery_provider = delivery_provider
        dispatch.delivery_reference = delivery_reference
        dispatch.delivery_status = "sent"
        dispatch.last_status_update_at = now
        return dispatch

    def mark_failed(self, dispatch: IncidentDispatch, *, failure_reason: str) -> IncidentDispatch:
        dispatch.status = "failed"
        dispatch.failure_reason = (failure_reason or "").strip() or None
        dispatch.delivery_status = "failed"
        dispatch.last_status_update_at = utc_now()
        return dispatch

    def mark_acknowledged(
        self,
        dispatch: IncidentDispatch,
        *,
        actor_user: User,
        acknowledged_by: str | None = None,
    ) -> IncidentDispatch:
        now = utc_now()
        dispatch.status = "acknowledged"
        dispatch.ack_status = "acknowledged"
        dispatch.ack_user_id = actor_user.id
        dispatch.acknowledged_by = acknowledged_by or getattr(actor_user, "name", None)
        dispatch.acknowledged_at = now
        dispatch.last_status_update_at = now
        return dispatch

    def mark_resolved(
        self,
        dispatch: IncidentDispatch,
        *,
        resolution_note: str | None = None,
        resolution_proof_url: str | None = None,
    ) -> IncidentDispatch:
        now = utc_now()
        dispatch.status = "resolved"
        dispatch.resolution_note = (resolution_note or "").strip() or None
        dispatch.resolution_proof_url = (resolution_proof_url or "").strip() or None
        dispatch.resolved_at = now
        dispatch.last_status_update_at = now
        return dispatch

    def attach_external_reference(
        self,
        dispatch: IncidentDispatch,
        *,
        reference_number: str,
        source: str | None = None,
    ) -> IncidentDispatch:
        dispatch.external_reference_number = (reference_number or "").strip() or None
        dispatch.external_reference_source = (source or "").strip() or None
        dispatch.last_status_update_at = utc_now()
        return dispatch

    def acknowledge_dispatch(
        self,
        dispatch_id: int,
        actor_user: User,
        note: str | None = None,
        channel: str = "internal_queue",
    ) -> tuple[bool, list[str]]:
        """Acknowledge a dispatch. Updates dispatch, writes event, transitions assigned -> acknowledged."""
        dispatch = db.session.get(IncidentDispatch, dispatch_id)
        if dispatch is None:
            return False, ["Dispatch not found."]
        if dispatch.ack_status == "acknowledged":
            return False, ["Dispatch already acknowledged."]

        user_authority_ids = [m.authority_id for m in actor_user.authority_memberships]
        is_admin = getattr(actor_user, "role", None) == "admin"
        if not is_admin and dispatch.authority_id not in user_authority_ids:
            return False, ["You do not have permission to acknowledge this dispatch."]

        incident = self.incident_repo.get_by_id(dispatch.incident_id)
        if incident is None:
            return False, ["Incident not found."]
        if incident.status != IncidentStatus.ASSIGNED.value:
            return False, ["Incident must be in assigned status to acknowledge."]

        self.mark_acknowledged(dispatch, actor_user=actor_user)

        current_ownership = self.ownership_repo.get_current(incident.id)
        if current_ownership is None or current_ownership.authority_id != dispatch.authority_id:
            self.ownership_repo.start_ownership(
                incident.id,
                dispatch.authority_id,
                assigned_by_user_id=actor_user.id,
                dispatch_id=dispatch.id,
                reason="Ownership set on acknowledgment",
            )

        self.event_repo.create(
            incident_id=incident.id,
            event_type=IncidentEventType.INCIDENT_ACKNOWLEDGED.value,
            from_status=IncidentStatus.ASSIGNED.value,
            to_status=IncidentStatus.ACKNOWLEDGED.value,
            actor_user_id=actor_user.id,
            actor_role=self._actor_role_from_user(actor_user),
            authority_id=dispatch.authority_id,
            dispatch_id=dispatch.id,
            note=note,
        )

        ok, errors = self.change_status(
            incident,
            IncidentStatus.ACKNOWLEDGED,
            actor_user_id=actor_user.id,
            actor_role=self._actor_role_from_user(actor_user),
            note=note or "Department acknowledged dispatch",
            authority_id=dispatch.authority_id,
            dispatch_id=dispatch.id,
        )
        if not ok:
            return False, errors
        db.session.commit()
        return True, []

    def acknowledge_incident(
        self,
        incident_id: int,
        actor_user: User,
        note: str | None = None,
    ) -> tuple[bool, list[str]]:
        """Acknowledge the latest pending dispatch for an incident. Convenience for UI."""
        user_authority_ids = [m.authority_id for m in actor_user.authority_memberships]
        is_admin = getattr(actor_user, "role", None) == "admin"

        stmt = (
            select(IncidentDispatch)
            .where(
                IncidentDispatch.incident_id == incident_id,
                IncidentDispatch.ack_status == "pending",
            )
            .order_by(IncidentDispatch.dispatched_at.desc())
        )
        if not is_admin:
            stmt = stmt.where(IncidentDispatch.authority_id.in_(user_authority_ids))
        dispatch = db.session.execute(stmt).scalars().first()
        if dispatch is None:
            return False, ["No pending dispatch found for this incident."]
        return self.acknowledge_dispatch(dispatch.id, actor_user, note=note)

    def can_acknowledge_incident(self, incident_id: int, user: User) -> bool:
        """True if user can acknowledge a pending dispatch for this incident."""
        if incident_id is None:
            return False
        incident = self.incident_repo.get_by_id(incident_id)
        if incident is None or incident.status != IncidentStatus.ASSIGNED.value:
            return False
        user_authority_ids = [m.authority_id for m in user.authority_memberships]
        is_admin = getattr(user, "role", None) == "admin"
        stmt = select(IncidentDispatch).where(
            IncidentDispatch.incident_id == incident_id,
            IncidentDispatch.ack_status == "pending",
        )
        if not is_admin:
            stmt = stmt.where(IncidentDispatch.authority_id.in_(user_authority_ids))
        return db.session.execute(stmt).scalars().first() is not None

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

        is_override = allow_admin_override and not self._is_valid_transition(
            current_status, to_status
        )
        if not allow_admin_override and not self._is_valid_transition(current_status, to_status):
            errors.append("Invalid status transition.")
            return False, errors

        effective_reason = (reason or note or "").strip()
        is_sensitive = (
            to_status == IncidentStatus.REJECTED
            or (current_status == IncidentStatus.RESOLVED and to_status == IncidentStatus.CLOSED)
            or is_override
        )
        if is_sensitive and not effective_reason:
            errors.append(
                "A reason is required for reject, manual close, reopen, and override actions."
            )
            return False, errors

        from_status = incident.status
        now = utc_now()

        incident.status = to_status.value
        incident.version += 1
        if to_status == IncidentStatus.ASSIGNED and incident.assigned_at is None:
            incident.assigned_at = now
        if to_status == IncidentStatus.ASSIGNED:
            incident.escalated_at = now
            incident.escalated_by_user_id = actor_user_id
        if to_status == IncidentStatus.ACKNOWLEDGED and incident.acknowledged_at is None:
            incident.acknowledged_at = now
        if to_status == IncidentStatus.SCREENED:
            incident.verified_at = now
            incident.verified_by_user_id = actor_user_id
        if to_status == IncidentStatus.RESOLVED:
            incident.resolved_at = now
        if to_status == IncidentStatus.CLOSED:
            incident.closed_at = now

        event_type = self._event_type_for_transition(
            from_status,
            to_status,
            actor_role=actor_role,
        )
        event = self.event_repo.create(
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
        db.session.flush()

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
            self._close_sla_tracking_if_needed(incident)

        if is_sensitive:
            if to_status == IncidentStatus.REJECTED:
                action = "incident_rejected"
            elif current_status == IncidentStatus.RESOLVED and to_status == IncidentStatus.CLOSED:
                action = "incident_manual_close"
            else:
                action = "incident_status_override"
            audit_service.log_incident_status(
                incident_id=incident.id,
                action=action,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                reason=effective_reason,
                before_status=from_status,
                after_status=to_status.value,
            )

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
            event_id=event.id,
        )
        if to_status not in (
            IncidentStatus.RESOLVED,
            IncidentStatus.CLOSED,
            IncidentStatus.REJECTED,
        ):
            self._upsert_sla_tracking(incident)
            self._refresh_sla_breach_state(incident)

        return True, []

    def _event_type_for_transition(
        self,
        from_status: str,
        to_status: IncidentStatus,
        *,
        actor_role: str | None = None,
    ) -> str:
        """Map transition to event type."""
        if to_status == IncidentStatus.AWAITING_EVIDENCE:
            return IncidentEventType.PROOF_REQUESTED.value
        if to_status == IncidentStatus.REJECTED:
            return IncidentEventType.INCIDENT_REJECTED.value
        if to_status == IncidentStatus.CLOSED:
            return IncidentEventType.INCIDENT_CLOSED.value
        if to_status == IncidentStatus.RESOLVED:
            if actor_role == "department":
                return IncidentEventType.AUTHORITY_RESOLUTION_UPDATE.value
            return IncidentEventType.INCIDENT_RESOLVED.value
        if to_status == IncidentStatus.IN_PROGRESS and actor_role == "department":
            return IncidentEventType.AUTHORITY_PROGRESS_UPDATE.value
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
            return target in {
                IncidentStatus.SCREENED,
                IncidentStatus.REJECTED,
                IncidentStatus.AWAITING_EVIDENCE,
            }
        if current == IncidentStatus.AWAITING_EVIDENCE:
            return target in {IncidentStatus.REPORTED, IncidentStatus.REJECTED}
        if current == IncidentStatus.SCREENED:
            return target in {
                IncidentStatus.ASSIGNED,
                IncidentStatus.REJECTED,
                IncidentStatus.AWAITING_EVIDENCE,
            }
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
