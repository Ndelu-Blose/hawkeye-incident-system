from app import create_app
from app.constants import Roles
from app.extensions import db
from app.models.user import User


def _create_user(email: str, role: str) -> User:
    user = User(
        name=email.split("@")[0],
        email=email,
        password_hash="test-hash",
        role=role,
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_incident_lifecycle():
    app = create_app("testing")
    client = app.test_client()

    with app.app_context():
        resident = _create_user("resident@example.com", Roles.RESIDENT.value)
        authority = _create_user("authority@example.com", Roles.AUTHORITY.value)

        # Log in as resident by setting session directly
        with client.session_transaction() as sess:
            sess["_user_id"] = str(resident.id)

        # Resident creates incident
        resp = client.post(
            "/resident/incidents/new",
            data={
                "title": "Broken street light",
                "description": "Street light not working",
                "category": "Lighting",
                "location": "Main street",
                "severity": "low",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

        # Log in as authority
        with client.session_transaction() as sess:
            sess["_user_id"] = str(authority.id)

        # View authority dashboard
        resp = client.get("/authority/dashboard")
        assert resp.status_code == 200

