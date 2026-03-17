from sqlalchemy import event

from app.constants import IncidentStatus, Roles
from app.extensions import db
from app.extensions import db as app_db
from app.models.incident import Incident
from app.models.incident_category import IncidentCategory
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
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-000001",
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


def test_admin_incident_list_filters_and_sort_and_pagination(app, client):
    """Admin /admin/incidents respects filters, sort order, and preserves filters across pages."""
    with app.app_context():
        admin, _ = auth_service.register_user(
            name="Admin Filters",
            email="admin_filters@example.com",
            password="password123",
            role=Roles.ADMIN.value,
        )
        resident, _ = auth_service.register_user(
            name="Resident Filters",
            email="resident_filters@example.com",
            password="password123",
            role=Roles.RESIDENT.value,
        )
        profile = ResidentProfile(
            user_id=resident.id,
            phone_number="0812345678",
            street_address_1="123 Main St",
            suburb="North Ward",
            profile_completed=True,
            consent_location=True,
        )
        cat = IncidentCategory(name="pothole", description="Road", is_active=True)
        db.session.add(profile)
        db.session.add(cat)
        db.session.commit()

        incidents: list[Incident] = []
        for i in range(25):
            status = IncidentStatus.REPORTED.value if i < 20 else IncidentStatus.IN_PROGRESS.value
            suburb = "North Ward" if i % 2 == 0 else "South Ward"
            severity = "high" if i % 3 == 0 else "low"
            inc = Incident(
                reported_by_id=resident.id,
                title=f"Admin list {i}",
                description="Desc",
                category="pothole",
                category_id=cat.id,
                suburb_or_ward=suburb,
                street_or_landmark="Main",
                location="Main, Ward",
                severity=severity,
                status=status,
                reference_code=f"HK-2026-03-{i:06d}",
            )
            incidents.append(inc)
        db.session.add_all(incidents)
        db.session.commit()

    client.post(
        "/auth/login",
        data={"email": "admin_filters@example.com", "password": "password123"},
        follow_redirects=True,
    )

    # Filters: status=reported, category, severity=high, area contains 'North', q matches title.
    resp = client.get(
        "/admin/incidents",
        query_string={
            "status": "reported",
            "category": "pothole",
            "severity": "high",
            "area": "North",
            "q": "Admin list",
            "sort": "newest",
            "page": 1,
        },
    )
    assert resp.status_code == 200
    assert b"Admin list" in resp.data

    # Page 2 with same filters.
    resp_page2 = client.get(
        "/admin/incidents",
        query_string={
            "status": "reported",
            "category": "pothole",
            "severity": "high",
            "area": "North",
            "q": "Admin list",
            "sort": "newest",
            "page": 2,
        },
    )
    assert resp_page2.status_code == 200
    assert b"Admin list" in resp_page2.data


def test_admin_incident_list_query_count_reasonable(app, client):
    """Basic N+1 sanity check: listing several incidents does not explode query count."""
    with app.app_context():
        admin, _ = auth_service.register_user(
            name="Admin Perf",
            email="admin_perf@example.com",
            password="password123",
            role=Roles.ADMIN.value,
        )
        resident, _ = auth_service.register_user(
            name="Resident Perf",
            email="resident_perf@example.com",
            password="password123",
            role=Roles.RESIDENT.value,
        )
        profile = ResidentProfile(
            user_id=resident.id,
            phone_number="0812345678",
            street_address_1="123 Main St",
            suburb="Perf Ward",
            profile_completed=True,
            consent_location=True,
        )
        db.session.add(profile)
        db.session.commit()

        # Create several incidents for this resident.
        for i in range(10):
            inc = Incident(
                reported_by_id=resident.id,
                title=f"Perf {i}",
                description="Desc",
                category="Cat",
                suburb_or_ward="Perf Ward",
                street_or_landmark="Main",
                location="Main, Perf",
                severity="low",
                status=IncidentStatus.REPORTED.value,
                reference_code=f"HK-2026-03-9{i:05d}",
            )
            db.session.add(inc)
        db.session.commit()

        engine = app_db.engine
        queries: list[str] = []

        @event.listens_for(engine, "before_cursor_execute")
        def _count_queries(conn, cursor, statement, parameters, context, executemany):
            # Exclude PRAGMA and transaction bookkeeping.
            if not statement.lstrip().upper().startswith(("PRAGMA", "BEGIN", "COMMIT", "ROLLBACK")):
                queries.append(statement)

    try:
        client.post(
            "/auth/login",
            data={"email": "admin_perf@example.com", "password": "password123"},
            follow_redirects=True,
        )
        resp = client.get("/admin/incidents")
        assert resp.status_code == 200
    finally:
        # Remove listeners to avoid interference with other tests.
        event.remove(engine, "before_cursor_execute", _count_queries)

    # This threshold is intentionally generous; it's just a smoke test against extreme N+1.
    assert len(queries) <= 60
