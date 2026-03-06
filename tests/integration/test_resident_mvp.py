"""Tests for Resident MVP: create with evidence, edit rule, dashboard, access control."""

import io

from app.constants import IncidentStatus, Roles
from app.extensions import db
from app.models.incident import Incident
from app.services.auth_service import auth_service
from app.services.incident_service import incident_service

from tests.conftest import MINIMAL_PNG_BYTES


def test_resident_dashboard_requires_login(client):
    resp = client.get("/resident/dashboard", follow_redirects=True)
    assert resp.status_code == 200
    assert b"login" in resp.data.lower() or b"Log in" in resp.data


def test_resident_dashboard_and_my_incidents(app, client):
    with app.app_context():
        auth_service.register_user(
            name="Resident One",
            email="r1@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
    client.post("/auth/login", data={"email": "r1@example.com", "password": "pass"}, follow_redirects=True)
    resp = client.get("/resident/dashboard")
    assert resp.status_code == 200
    assert b"Resident One" in resp.data or b"Welcome" in resp.data
    resp = client.get("/resident/incidents")
    assert resp.status_code == 200


def test_resident_create_incident_requires_evidence(app, client):
    with app.app_context():
        auth_service.register_user(
            name="Resident",
            email="res@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
    client.post("/auth/login", data={"email": "res@example.com", "password": "pass"}, follow_redirects=True)
    resp = client.post(
        "/resident/incidents/new",
        data={
            "title": "Test",
            "description": "Desc",
            "category": "Cat",
            "suburb_or_ward": "Sub",
            "street_or_landmark": "Street",
            "severity": "low",
            "confirm_real": "1",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"evidence" in resp.data.lower() or b"image" in resp.data.lower() or b"required" in resp.data.lower()


def test_resident_can_edit_only_pending_incident(app, client):
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="edit@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        incident = Incident(
            reported_by_id=user.id,
            title="Original",
            description="Desc",
            category="Cat",
            suburb_or_ward="Sub",
            street_or_landmark="St",
            location="St, Sub",
            severity="low",
            status=IncidentStatus.PENDING.value,
        )
        db.session.add(incident)
        db.session.commit()
        incident_id = incident.id

    client.post("/auth/login", data={"email": "edit@example.com", "password": "pass"}, follow_redirects=True)

    resp = client.get(f"/resident/incidents/{incident_id}/edit")
    assert resp.status_code == 200

    resp = client.post(
        f"/resident/incidents/{incident_id}/edit",
        data={
            "title": "Updated title",
            "description": "Updated desc",
            "category": "Cat",
            "suburb_or_ward": "Sub",
            "street_or_landmark": "St",
            "severity": "medium",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        incident = db.session.get(Incident, incident_id)
        assert incident.title == "Updated title"
        assert incident.severity == "medium"


def test_resident_cannot_edit_non_pending_incident(app, client):
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="noedit@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        incident = Incident(
            reported_by_id=user.id,
            title="In Progress",
            description="Desc",
            category="Cat",
            suburb_or_ward="Sub",
            street_or_landmark="St",
            location="St, Sub",
            severity="low",
            status=IncidentStatus.IN_PROGRESS.value,
        )
        db.session.add(incident)
        db.session.commit()
        incident_id = incident.id

    client.post("/auth/login", data={"email": "noedit@example.com", "password": "pass"}, follow_redirects=True)
    resp = client.get(f"/resident/incidents/{incident_id}/edit", follow_redirects=True)
    assert resp.status_code == 200
    assert b"no longer be edited" in resp.data or b"redirect" in resp.data.lower()


def test_resident_cannot_view_other_residents_incident(app, client):
    with app.app_context():
        auth_service.register_user(
            name="Resident A",
            email="a@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        user_b, _ = auth_service.register_user(
            name="Resident B",
            email="b@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        incident = Incident(
            reported_by_id=user_b.id,
            title="B's incident",
            description="Desc",
            category="Cat",
            suburb_or_ward="Sub",
            street_or_landmark="St",
            location="St, Sub",
            severity="low",
            status=IncidentStatus.PENDING.value,
        )
        db.session.add(incident)
        db.session.commit()
        incident_id = incident.id

    client.post("/auth/login", data={"email": "a@example.com", "password": "pass"}, follow_redirects=True)
    resp = client.get(f"/resident/incidents/{incident_id}", follow_redirects=True)
    assert resp.status_code == 200
    assert b"do not have access" in resp.data or b"not found" in resp.data.lower()


def test_suggest_similar_for_resident(app):
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="sim@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        incident = Incident(
            reported_by_id=user.id,
            title="First",
            description="D",
            category="Vandalism",
            suburb_or_ward="North",
            street_or_landmark="High St",
            location="High St, North",
            severity="low",
            status=IncidentStatus.PENDING.value,
        )
        db.session.add(incident)
        db.session.commit()

        similar = incident_service.suggest_similar_for_resident("Vandalism", "North")
        assert len(similar) >= 1
        assert similar[0].category == "Vandalism"
        assert similar[0].suburb_or_ward == "North"

        similar_none = incident_service.suggest_similar_for_resident("Other", "South")
        assert len(similar_none) == 0


def test_can_resident_edit_helper(app):
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="helper@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        pending = Incident(
            reported_by_id=user.id,
            title="P",
            description="D",
            category="C",
            suburb_or_ward="S",
            street_or_landmark="St",
            location="St, S",
            severity="low",
            status=IncidentStatus.PENDING.value,
        )
        in_progress = Incident(
            reported_by_id=user.id,
            title="P2",
            description="D",
            category="C",
            suburb_or_ward="S",
            street_or_landmark="St",
            location="St, S",
            severity="low",
            status=IncidentStatus.IN_PROGRESS.value,
        )
        db.session.add_all([pending, in_progress])
        db.session.commit()

        assert incident_service.can_resident_edit(pending, user) is True
        assert incident_service.can_resident_edit(in_progress, user) is False
