
from app.constants import IncidentStatus, Roles
from app.extensions import db
from app.models.incident import Incident
from app.models.resident_profile import ResidentProfile
from app.services.auth_service import auth_service


def test_admin_incident_console_requires_admin(app, client):
    with app.app_context():
        auth_service.register_user(
            name="Resident",
            email="resident_admincheck@example.com",
            password="password123",
            role=Roles.RESIDENT.value,
        )

    client.post(
        "/auth/login",
        data={"email": "resident_admincheck@example.com", "password": "password123"},
        follow_redirects=True,
    )

    resp = client.get("/admin/incidents")
    assert resp.status_code == 403


def test_admin_status_update_visible_to_resident(app, client):
    with app.app_context():
        resident, _ = auth_service.register_user(
            name="Resident One",
            email="resident_visibility@example.com",
            password="password123",
            role=Roles.RESIDENT.value,
        )
        admin, _ = auth_service.register_user(
            name="Admin One",
            email="admin_visibility@example.com",
            password="password123",
            role=Roles.ADMIN.value,
        )

        profile = ResidentProfile(
            user_id=resident.id,
            phone_number="0812345678",
            street_address_1="123 Main St",
            suburb="Test Suburb",
            profile_completed=True,
            consent_location=True,
        )
        db.session.add(profile)

        incident = Incident(
            reported_by_id=resident.id,
            title="Test incident",
            description="Desc",
            category="Cat",
            suburb_or_ward="Ward 1",
            street_or_landmark="Main street",
            location="Main street, Ward 1",
            severity="low",
            status=IncidentStatus.PENDING.value,
        )
        db.session.add(incident)
        db.session.commit()
        incident_id = incident.id

    client.post(
        "/auth/login",
        data={"email": "admin_visibility@example.com", "password": "password123"},
        follow_redirects=True,
    )

    resp = client.get("/admin/incidents")
    assert resp.status_code == 200

    note = "Admin moved this forward"
    resp = client.post(
        f"/admin/incidents/{incident_id}/status",
        data={"status": "in_progress", "note": note},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Switch to resident and confirm status + note appear on their detail page.
    client.get("/auth/logout", follow_redirects=True)
    client.post(
        "/auth/login",
        data={"email": "resident_visibility@example.com", "password": "password123"},
        follow_redirects=True,
    )

    resp = client.get(f"/resident/incidents/{incident_id}")
    assert resp.status_code == 200
    assert b"In Progress" in resp.data
    assert note.encode() in resp.data
