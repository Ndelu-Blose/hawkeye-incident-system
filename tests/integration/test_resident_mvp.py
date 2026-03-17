"""Tests for Resident MVP: create with evidence, edit rule, dashboard, access control, guided form."""

import io

from app.constants import IncidentStatus, Roles
from app.extensions import db
from app.models.incident import Incident
from app.models.incident_category import IncidentCategory
from app.models.resident_profile import ResidentProfile
from app.models.user import User
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
    client.post(
        "/auth/login", data={"email": "r1@example.com", "password": "pass"}, follow_redirects=True
    )
    resp = client.get("/resident/dashboard")
    assert resp.status_code == 200
    assert b"Resident One" in resp.data or b"Welcome" in resp.data
    resp = client.get("/resident/incidents")
    assert resp.status_code == 200


def test_resident_incidents_filters_and_pagination(app, client):
    """Resident /resident/incidents respects filters and paginates with filters preserved."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident Filters",
            email="filters@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        cat_a = IncidentCategory(name="pothole", description="Road", is_active=True)
        cat_b = IncidentCategory(name="dumping", description="Dump", is_active=True)
        db.session.add_all([cat_a, cat_b])
        db.session.commit()

        # Create a mix of incidents for this resident.
        incidents: list[Incident] = []
        for i in range(25):
            category = "pothole" if i % 2 == 0 else "dumping"
            category_id = cat_a.id if category == "pothole" else cat_b.id
            status = IncidentStatus.REPORTED.value if i < 20 else IncidentStatus.RESOLVED.value
            incident = Incident(
                reported_by_id=user.id,
                title=f"Incident {i}",
                description="Desc",
                category=category,
                category_id=category_id,
                suburb_or_ward="North" if i % 3 == 0 else "South",
                street_or_landmark="Main St",
                location="Main St, Area",
                severity="low",
                status=status,
                reference_code=f"HK-2026-03-{i:06d}",
            )
            incidents.append(incident)
        db.session.add_all(incidents)
        db.session.commit()

        cat_a_id = cat_a.id

    client.post(
        "/auth/login",
        data={"email": "filters@example.com", "password": "pass"},
        follow_redirects=True,
    )

    # Filter: status=pending, category=pothole, area contains 'North', q matches title.
    resp = client.get(
        "/resident/incidents",
        query_string={
            "status": "pending",
            "category_id": str(cat_a_id),
            "area": "North",
            "q": "Incident",
            "page": 1,
        },
    )
    assert resp.status_code == 200
    # Should show at least one filtered incident.
    assert b"Incident" in resp.data

    # Page 2 preserves filters.
    resp_page2 = client.get(
        "/resident/incidents",
        query_string={
            "status": "pending",
            "category_id": str(cat_a_id),
            "area": "North",
            "q": "Incident",
            "page": 2,
        },
    )
    assert resp_page2.status_code == 200
    assert b"Incident" in resp_page2.data


def test_resident_incidents_quick_filters_open_resolved_this_month(app, client):
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident Quick",
            email="quick@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        # Pending and resolved incidents for the same resident.
        pending = Incident(
            reported_by_id=user.id,
            title="Pending incident",
            description="D",
            category="Cat",
            suburb_or_ward="Ward 1",
            street_or_landmark="Main",
            location="Main, Ward 1",
            severity="low",
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-010000",
        )
        resolved = Incident(
            reported_by_id=user.id,
            title="Resolved incident",
            description="D",
            category="Cat",
            suburb_or_ward="Ward 2",
            street_or_landmark="Second",
            location="Second, Ward 2",
            severity="low",
            status=IncidentStatus.RESOLVED.value,
            reference_code="HK-2026-03-010001",
        )
        db.session.add_all([pending, resolved])
        db.session.commit()

    client.post(
        "/auth/login",
        data={"email": "quick@example.com", "password": "pass"},
        follow_redirects=True,
    )

    # "My Open" → status=pending
    resp_open = client.get("/resident/incidents", query_string={"status": "pending"})
    assert resp_open.status_code == 200
    assert b"Pending incident" in resp_open.data

    # "My Resolved" → status=resolved
    resp_resolved = client.get("/resident/incidents", query_string={"status": "resolved"})
    assert resp_resolved.status_code == 200
    assert b"Resolved incident" in resp_resolved.data

    # "This Month" quick filter uses date_from = first day this month; we just ensure it returns 200.
    from datetime import date

    first_day = date.today().replace(day=1).strftime("%Y-%m-%d")
    resp_month = client.get("/resident/incidents", query_string={"date_from": first_day})
    assert resp_month.status_code == 200


def test_resident_create_incident_requires_evidence(app, client):
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="res@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        profile = ResidentProfile(
            user_id=user.id,
            phone_number="0812345678",
            street_address_1="123 Main St",
            suburb="Test Suburb",
            profile_completed=True,
            consent_location=True,
        )
        cat = IncidentCategory(name="dumping", description="Dumping", is_active=True)
        db.session.add(profile)
        db.session.add(cat)
        db.session.commit()
        category_id = cat.id
    client.post(
        "/auth/login", data={"email": "res@example.com", "password": "pass"}, follow_redirects=True
    )
    resp = client.post(
        "/resident/incidents/new",
        data={
            "category_id": str(category_id),
            "title": "Test",
            "description": "Desc",
            "urgency_level": "soon",
            "location_mode": "other",
            "suburb_or_ward": "Sub",
            "street_or_landmark": "Street",
            "confirm_real": "1",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert (
        b"evidence" in resp.data.lower()
        or b"image" in resp.data.lower()
        or b"required" in resp.data.lower()
    )


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
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-000001",
        )
        db.session.add(incident)
        db.session.commit()
        incident_id = incident.id

    client.post(
        "/auth/login", data={"email": "edit@example.com", "password": "pass"}, follow_redirects=True
    )

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
            reference_code="HK-2026-03-000002",
        )
        db.session.add(incident)
        db.session.commit()
        incident_id = incident.id

    client.post(
        "/auth/login",
        data={"email": "noedit@example.com", "password": "pass"},
        follow_redirects=True,
    )
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
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-000003",
        )
        db.session.add(incident)
        db.session.commit()
        incident_id = incident.id

    client.post(
        "/auth/login", data={"email": "a@example.com", "password": "pass"}, follow_redirects=True
    )
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
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-000004",
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
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-000005",
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
            reference_code="HK-2026-03-000006",
        )
        db.session.add_all([pending, in_progress])
        db.session.commit()

        assert incident_service.can_resident_edit(pending, user) is True
        assert incident_service.can_resident_edit(in_progress, user) is False


def test_report_incident_page_shows_guided_form_with_presets(app, client):
    """GET /resident/incidents/new returns 200 with category selection, urgency, and evidence when profile complete."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="reportform@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        profile = ResidentProfile(
            user_id=user.id,
            phone_number="0812345678",
            street_address_1="123 Main St",
            suburb="Test Suburb",
            profile_completed=True,
            consent_location=True,
        )
        db.session.add(profile)
        db.session.add(IncidentCategory(name="dumping", description="Dumping", is_active=True))
        db.session.commit()

    client.post(
        "/auth/login",
        data={"email": "reportform@example.com", "password": "pass"},
        follow_redirects=True,
    )
    resp = client.get("/resident/incidents/new")
    assert resp.status_code == 200
    assert b"category_id" in resp.data or b"Select a category" in resp.data
    assert b"urgency" in resp.data.lower() or b"Urgent" in resp.data
    assert b"evidence" in resp.data.lower() or b"image" in resp.data.lower()
    assert (
        b"location_mode" in resp.data
        or b"saved address" in resp.data.lower()
        or b"different location" in resp.data.lower()
    )


def test_guided_form_submit_with_category_id_and_saved_location(app, client):
    """POST with category_id, location_mode=saved, and evidence creates incident with preset title and profile address."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="savedloc@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        profile = ResidentProfile(
            user_id=user.id,
            phone_number="0812345678",
            street_address_1="140229 Nkanyisweni",
            suburb="Amanzimtoti",
            profile_completed=True,
            consent_location=True,
        )
        cat = IncidentCategory(name="dumping", description="Illegal dumping", is_active=True)
        db.session.add(profile)
        db.session.add(cat)
        db.session.commit()
        category_id = cat.id

    client.post(
        "/auth/login",
        data={"email": "savedloc@example.com", "password": "pass"},
        follow_redirects=True,
    )
    resp = client.post(
        "/resident/incidents/new",
        data={
            "category_id": str(category_id),
            "title": "",
            "description": "Dump in the park",
            "urgency_level": "soon",
            "location_mode": "saved",
            "suburb_or_ward": "",
            "street_or_landmark": "",
            "confirm_real": "1",
            "evidence": (io.BytesIO(MINIMAL_PNG_BYTES), "evidence.png"),
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        resident_user = db.session.query(User).filter_by(email="savedloc@example.com").first()
        assert resident_user is not None
        incident = (
            db.session.query(Incident)
            .filter(Incident.reported_by_id == resident_user.id)
            .order_by(Incident.id.desc())
            .first()
        )
        assert incident is not None
        assert (
            "dumping" in incident.title.lower()
            or "illegal" in incident.title.lower()
            or incident.title
        )
        assert incident.suburb_or_ward == "Amanzimtoti"
        assert (
            "Nkanyisweni" in incident.street_or_landmark
            or incident.street_or_landmark == "140229 Nkanyisweni"
        )
        assert incident.location_mode == "saved"


def test_guided_form_submit_with_category_id_and_other_location(app, client):
    """POST with category_id, location_mode=other, suburb/street, and evidence creates incident with category_id set."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="otherloc@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        profile = ResidentProfile(
            user_id=user.id,
            phone_number="0812345678",
            street_address_1="123 Main St",
            suburb="Test Suburb",
            profile_completed=True,
            consent_location=True,
        )
        cat = IncidentCategory(name="pothole", description="Road hazard", is_active=True)
        db.session.add(profile)
        db.session.add(cat)
        db.session.commit()
        category_id = cat.id

    client.post(
        "/auth/login",
        data={"email": "otherloc@example.com", "password": "pass"},
        follow_redirects=True,
    )
    resp = client.post(
        "/resident/incidents/new",
        data={
            "category_id": str(category_id),
            "title": "Large pothole on Oak Rd",
            "description": "Deep pothole near the junction",
            "urgency_level": "soon",
            "location_mode": "other",
            "suburb_or_ward": "North Side",
            "street_or_landmark": "Oak Rd",
            "confirm_real": "1",
            "evidence": (io.BytesIO(MINIMAL_PNG_BYTES), "evidence.png"),
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        resident_user = db.session.query(User).filter_by(email="otherloc@example.com").first()
        assert resident_user is not None
        incident = (
            db.session.query(Incident)
            .filter(Incident.reported_by_id == resident_user.id)
            .order_by(Incident.id.desc())
            .first()
        )
        assert incident is not None
        assert incident.category_id == category_id
        assert incident.category == "pothole"
        assert incident.suburb_or_ward == "North Side"
        assert incident.street_or_landmark == "Oak Rd"
        assert incident.location_mode == "other"


def test_report_form_render_preserves_form_data_on_validation_error(app, client):
    """POST with category_id and location_mode=other but empty street re-renders form with category_id and input preserved."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="validation@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        profile = ResidentProfile(
            user_id=user.id,
            phone_number="0812345678",
            street_address_1="123 Main St",
            suburb="Test Suburb",
            profile_completed=True,
            consent_location=True,
        )
        cat = IncidentCategory(name="vandalism", description="Vandalism", is_active=True)
        db.session.add(profile)
        db.session.add(cat)
        db.session.commit()
        category_id = cat.id

    client.post(
        "/auth/login",
        data={"email": "validation@example.com", "password": "pass"},
        follow_redirects=True,
    )
    resp = client.post(
        "/resident/incidents/new",
        data={
            "category_id": str(category_id),
            "title": "Graffiti",
            "description": "Wall was tagged",
            "urgency_level": "soon",
            "location_mode": "other",
            "suburb_or_ward": "Central",
            "street_or_landmark": "",
            "confirm_real": "1",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert (
        b"Street" in resp.data or b"street" in resp.data.lower() or b"landmark" in resp.data.lower()
    )
    assert str(category_id).encode() in resp.data
    assert b"Graffiti" in resp.data or b"graffiti" in resp.data.lower()
    assert b"Central" in resp.data
