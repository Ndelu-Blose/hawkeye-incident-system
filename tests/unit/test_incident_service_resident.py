"""Unit tests for IncidentService resident flows: create with media, edit by resident, guided wizard."""

import io

from werkzeug.datastructures import FileStorage

from app.constants import IncidentStatus, Roles
from app.extensions import db
from app.models.incident import Incident
from app.models.incident_category import IncidentCategory
from app.models.resident_profile import ResidentProfile
from app.models.user import User
from app.services.auth_service import auth_service
from app.services.incident_service import incident_service
from tests.conftest import MINIMAL_PNG_BYTES


def test_create_incident_with_evidence(app):
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="create@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        payload = {
            "title": "Test incident",
            "description": "Description",
            "category": "Category",
            "suburb_or_ward": "Suburb",
            "street_or_landmark": "Main St",
            "severity": "low",
        }
        files = [FileStorage(stream=io.BytesIO(MINIMAL_PNG_BYTES), filename="evidence.png")]
        incident, errors = incident_service.create_incident(payload, user, files=files)
        assert incident is not None
        assert not errors
        assert incident.suburb_or_ward == "Suburb"
        assert incident.street_or_landmark == "Main St"
        assert incident.location == "Main St, Suburb"
        media_count = incident.media.count()
        assert media_count >= 1


def test_create_incident_without_evidence_fails(app):
    with app.app_context():
        auth_service.register_user("U", "nofile@example.com", "pass", Roles.RESIDENT.value)
        user = db.session.query(User).filter_by(email="nofile@example.com").first()
        assert user is not None
        payload = {
            "title": "T",
            "description": "D",
            "category": "C",
            "suburb_or_ward": "S",
            "street_or_landmark": "St",
            "severity": "low",
        }
        incident, errors = incident_service.create_incident(payload, user, files=None)
        assert incident is None
        assert any("evidence" in e.lower() or "image" in e.lower() for e in errors)


def test_update_incident_by_resident_success(app):
    with app.app_context():
        user, _ = auth_service.register_user("Res", "upd@example.com", "pass", Roles.RESIDENT.value)
        incident = Incident(
            reported_by_id=user.id,
            title="Original",
            description="D",
            category="C",
            suburb_or_ward="S",
            street_or_landmark="St",
            location="St, S",
            severity="low",
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-000001",
        )
        db.session.add(incident)
        db.session.commit()
        incident_id = incident.id

        payload = {
            "title": "Updated",
            "description": "New desc",
            "category": "C",
            "suburb_or_ward": "S",
            "street_or_landmark": "St",
            "severity": "high",
        }
        updated, errors = incident_service.update_incident_by_resident(incident_id, user, payload)
        assert updated is not None
        assert not errors
        assert updated.title == "Updated"
        assert updated.severity == "high"


def test_update_incident_by_resident_rejected_when_not_pending(app):
    with app.app_context():
        user, _ = auth_service.register_user(
            "Res", "nopend@example.com", "pass", Roles.RESIDENT.value
        )
        incident = Incident(
            reported_by_id=user.id,
            title="In Progress",
            description="D",
            category="C",
            suburb_or_ward="S",
            street_or_landmark="St",
            location="St, S",
            severity="low",
            status=IncidentStatus.IN_PROGRESS.value,
            reference_code="HK-2026-03-000002",
        )
        db.session.add(incident)
        db.session.commit()
        payload = {
            "title": "Updated",
            "description": "D",
            "category": "C",
            "suburb_or_ward": "S",
            "street_or_landmark": "St",
            "severity": "low",
        }
        updated, errors = incident_service.update_incident_by_resident(incident.id, user, payload)
        assert updated is None
        assert any("reported" in e.lower() for e in errors)


def test_create_incident_preset_title_and_urgency(app):
    """With category_id and no title, title is filled from preset; urgency_level maps to severity."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="preset@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        cat = IncidentCategory(
            name="dumping",
            description="Illegal dumping",
            is_active=True,
        )
        db.session.add(cat)
        db.session.commit()
        payload = {
            "category_id": str(cat.id),
            "category": "dumping",
            "title": "",
            "description": "Dump in the park",
            "suburb_or_ward": "North",
            "street_or_landmark": "Park Rd",
            "urgency_level": "soon",
        }
        files = [FileStorage(stream=io.BytesIO(MINIMAL_PNG_BYTES), filename="e.png")]
        incident, errors = incident_service.create_incident(payload, user, files=files)
        assert incident is not None
        assert not errors
        assert incident.title == "Illegal dumping reported"
        assert incident.severity == "medium"
        assert incident.urgency_level == "soon"


def test_create_incident_guided_fields_persisted(app):
    """location_mode, is_happening_now, is_anyone_in_danger, urgency_level are stored."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="guided@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        payload = {
            "title": "Suspicious person",
            "description": "Seen near the school",
            "category": "Other",
            "suburb_or_ward": "Sub",
            "street_or_landmark": "St",
            "severity": "high",
            "location_mode": "other",
            "urgency_level": "urgent_now",
            "is_happening_now": "1",
            "is_anyone_in_danger": "0",
        }
        files = [FileStorage(stream=io.BytesIO(MINIMAL_PNG_BYTES), filename="e.png")]
        incident, errors = incident_service.create_incident(payload, user, files=files)
        assert incident is not None
        assert not errors
        assert incident.location_mode == "other"
        assert incident.urgency_level == "urgent_now"
        assert incident.is_happening_now is True
        # Boolean questions that apply should persist False when the box was shown but not checked
        assert incident.is_anyone_in_danger is False


def test_create_incident_location_mode_saved_fills_from_profile(app):
    """When location_mode=saved and suburb/street empty, fill from resident profile."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="savedloc@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        profile = ResidentProfile(
            user_id=user.id,
            suburb="Amanzimtoti",
            street_address_1="140229 Nkanyisweni",
            profile_completed=True,
            consent_location=True,
        )
        db.session.add(profile)
        db.session.commit()
        payload = {
            "title": "Pothole",
            "description": "Large pothole",
            "category": "Other",
            "suburb_or_ward": "",
            "street_or_landmark": "",
            "severity": "medium",
            "location_mode": "saved",
        }
        files = [FileStorage(stream=io.BytesIO(MINIMAL_PNG_BYTES), filename="e.png")]
        incident, errors = incident_service.create_incident(payload, user, files=files)
        assert incident is not None
        assert not errors
        assert incident.suburb_or_ward == "Amanzimtoti"
        assert incident.street_or_landmark == "140229 Nkanyisweni"
        assert incident.location_mode == "saved"


def test_guided_boolean_none_when_question_not_asked(app):
    """If a preset marks a question as not applicable, the DB field stays None."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="guided-none@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        # Category with ask_is_anyone_in_danger = False in presets (e.g. vandalism)
        cat = IncidentCategory(
            name="vandalism",
            description="Damage to property",
            is_active=True,
        )
        db.session.add(cat)
        db.session.commit()
        payload = {
            "category_id": str(cat.id),
            "category": "vandalism",
            "title": "Graffiti",
            "description": "Graffiti on the wall",
            "suburb_or_ward": "North",
            "street_or_landmark": "Main Rd",
            "severity": "medium",
            # No guided boolean fields submitted; question is not asked by preset.
        }
        files = [FileStorage(stream=io.BytesIO(MINIMAL_PNG_BYTES), filename="e.png")]
        incident, errors = incident_service.create_incident(payload, user, files=files)
        assert incident is not None
        assert not errors
        # For vandalism, we only ask "is_issue_still_present", not "is_anyone_in_danger".
        assert incident.is_anyone_in_danger is None


def test_create_incident_sets_reference_code_with_expected_format(app):
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="ref-format@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        payload = {
            "title": "Ref format test",
            "description": "Desc",
            "category": "Cat",
            "suburb_or_ward": "Suburb",
            "street_or_landmark": "Main St",
            "severity": "low",
        }
        files = [FileStorage(stream=io.BytesIO(MINIMAL_PNG_BYTES), filename="evidence.png")]
        incident, errors = incident_service.create_incident(payload, user, files=files)
        assert incident is not None
        assert not errors
        assert incident.reference_code is not None

        # HK-YYYY-MM-XXXXXX where X is a digit.
        import re

        assert re.fullmatch(r"HK-\d{4}-\d{2}-\d{6}", incident.reference_code) is not None


def test_create_multiple_incidents_produces_distinct_reference_codes(app):
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="ref-multi@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        base_payload = {
            "title": "Incident",
            "description": "Desc",
            "category": "Cat",
            "suburb_or_ward": "Suburb",
            "street_or_landmark": "Main St",
            "severity": "low",
        }
        files = [FileStorage(stream=io.BytesIO(MINIMAL_PNG_BYTES), filename="evidence.png")]

        codes: set[str] = set()
        for i in range(3):
            payload = dict(base_payload)
            payload["title"] = f"Incident {i}"
            incident, errors = incident_service.create_incident(payload, user, files=files)
            assert incident is not None
            assert not errors
            assert incident.reference_code not in codes
            codes.add(incident.reference_code)


def test_create_incident_populates_validated_location_when_service_configured(app, monkeypatch):
    """When location_service is configured and returns a result, structured fields are populated."""
    from app.services import incident_service as incident_service_module
    from app.services import location_service as location_service_module

    class DummyGeocoded:
        def __init__(self) -> None:
            self.latitude = -29.123456
            self.longitude = 31.123456
            self.validated_address = "123 Main St, Test Suburb"
            self.suburb = "Test Suburb"
            self.ward = "Ward 10"

    class DummyService:
        def is_configured(self) -> bool:
            return True

        def geocode(self, address: str):
            return DummyGeocoded()

    with app.app_context():
        # Patch the global location_service used by IncidentService and refresh the IncidentService module reference.
        service_instance = DummyService()
        monkeypatch.setattr(location_service_module, "location_service", service_instance)
        monkeypatch.setattr(incident_service_module, "location_service", service_instance)

        user, _ = auth_service.register_user(
            name="Resident",
            email="geo@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        payload = {
            "title": "Geo test",
            "description": "Desc",
            "category": "Cat",
            "suburb_or_ward": "Suburb",
            "street_or_landmark": "Main St",
            "severity": "low",
        }
        files = [FileStorage(stream=io.BytesIO(MINIMAL_PNG_BYTES), filename="evidence.png")]
        incident, errors = incident_service.create_incident(payload, user, files=files)
        assert incident is not None
        assert not errors
        assert incident.location_validated is True
        assert incident.latitude is not None and incident.longitude is not None
        assert incident.validated_address == "123 Main St, Test Suburb"
        assert incident.suburb == "Test Suburb"
        assert incident.ward == "Ward 10"
