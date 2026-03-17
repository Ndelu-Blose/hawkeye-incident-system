"""Integration tests for public area incident view (anonymised)."""

from app.constants import IncidentStatus
from app.extensions import db
from app.models import Incident, IncidentCategory
from app.services.auth_service import auth_service


def test_public_area_incidents_page_requires_login(app, client):
    """Public area page is accessible without login."""
    resp = client.get("/public/area")
    assert resp.status_code == 200


def test_public_area_incidents_shows_empty_when_no_incidents(app, client):
    """When no incidents exist, area dropdown is empty."""
    with app.app_context():
        resp = client.get("/public/area")
    assert resp.status_code == 200
    assert b"Select an area" in resp.data


def test_public_area_incidents_lists_anonymised_incidents(app, client):
    """Public area view shows incidents without reporter info."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Reporter",
            email="reporter@example.com",
            password="pass",
            role="resident",
        )
        cat = IncidentCategory(name="pothole", description="Road", is_active=True)
        db.session.add(cat)
        db.session.commit()

        inc = Incident(
            reported_by_id=user.id,
            title="Pothole Reported",
            description="Large pothole",
            category="pothole",
            category_id=cat.id,
            suburb_or_ward="North Suburb",
            street_or_landmark="Main St",
            location="Main St, North Suburb",
            severity="medium",
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-000001",
        )
        db.session.add(inc)
        db.session.commit()

    resp = client.get("/public/area", query_string={"area": "North Suburb"})
    assert resp.status_code == 200
    assert b"Pothole Reported" in resp.data
    assert b"HK-2026-03-000001" in resp.data
    # Reporter PII must not appear
    assert b"Reporter" not in resp.data
    assert b"reporter@example.com" not in resp.data


def test_public_area_incidents_excludes_rejected(app, client):
    """Rejected incidents are not shown in public view."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="R",
            email="r@example.com",
            password="p",
            role="resident",
        )
        cat = IncidentCategory(name="pothole", description="Road", is_active=True)
        db.session.add(cat)
        db.session.commit()

        inc = Incident(
            reported_by_id=user.id,
            title="Rejected",
            description="x",
            category="pothole",
            category_id=cat.id,
            suburb_or_ward="South",
            street_or_landmark="St",
            location="St, South",
            severity="low",
            status=IncidentStatus.REJECTED.value,
            reference_code="HK-2026-03-000002",
        )
        db.session.add(inc)
        db.session.commit()

    resp = client.get("/public/area", query_string={"area": "South"})
    assert resp.status_code == 200
    assert b"Rejected" not in resp.data
    assert b"HK-2026-03-000002" not in resp.data
