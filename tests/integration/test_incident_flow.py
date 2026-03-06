import io

from app.constants import Roles
from app.services.auth_service import auth_service
from tests.conftest import MINIMAL_PNG_BYTES


def test_incident_lifecycle(app, client):
    # Create users with real hashed passwords via the auth service
    with app.app_context():
        resident, errors_resident = auth_service.register_user(
            name="Resident User",
            email="resident@example.com",
            password="password123",
            role=Roles.RESIDENT.value,
        )
        authority, errors_authority = auth_service.register_user(
            name="Authority User",
            email="authority@example.com",
            password="password123",
            role=Roles.AUTHORITY.value,
        )
        assert not errors_resident
        assert not errors_authority

    # Log in as resident through the real login route
    resp = client.post(
        "/auth/login",
        data={"email": "resident@example.com", "password": "password123"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Resident creates incident (structured location + at least one evidence image)
    resp = client.post(
        "/resident/incidents/new",
        data={
            "title": "Broken street light",
            "description": "Street light not working",
            "category": "Lighting",
            "suburb_or_ward": "Downtown",
            "street_or_landmark": "Main street",
            "severity": "low",
            "confirm_real": "1",
            "evidence": (io.BytesIO(MINIMAL_PNG_BYTES), "evidence.png"),
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Log out resident
    resp = client.get("/auth/logout", follow_redirects=True)
    assert resp.status_code == 200

    # Log in as authority via login route
    resp = client.post(
        "/auth/login",
        data={"email": "authority@example.com", "password": "password123"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # View authority dashboard
    resp = client.get("/authority/dashboard")
    assert resp.status_code == 200
