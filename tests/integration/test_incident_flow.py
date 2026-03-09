import io

from app.constants import Roles
from app.extensions import db
from app.models.incident_category import IncidentCategory
from app.models.resident_profile import ResidentProfile
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

        # Resident needs completed profile and a category to use the guided report form
        profile = ResidentProfile(
            user_id=resident.id,
            phone_number="0812345678",
            street_address_1="123 Main St",
            suburb="Downtown",
            profile_completed=True,
            consent_location=True,
        )
        cat = IncidentCategory(
            name="broken_streetlight",
            description="Street light not working",
            is_active=True,
        )
        db.session.add(profile)
        db.session.add(cat)
        db.session.commit()
        category_id = cat.id

    # Log in as resident through the real login route
    resp = client.post(
        "/auth/login",
        data={"email": "resident@example.com", "password": "password123"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Resident creates incident via guided form (category_id, urgency_level, location_mode, evidence)
    resp = client.post(
        "/resident/incidents/new",
        data={
            "category_id": str(category_id),
            "title": "Broken street light",
            "description": "Street light not working",
            "urgency_level": "soon",
            "location_mode": "other",
            "suburb_or_ward": "Downtown",
            "street_or_landmark": "Main street",
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
