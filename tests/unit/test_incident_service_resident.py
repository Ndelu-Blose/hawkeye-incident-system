"""Unit tests for IncidentService resident flows: create with media, edit by resident."""

import io

from werkzeug.datastructures import FileStorage

from app.constants import IncidentStatus, Roles
from app.extensions import db
from app.models.incident import Incident
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
            status=IncidentStatus.PENDING.value,
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
        assert any("pending" in e.lower() for e in errors)
