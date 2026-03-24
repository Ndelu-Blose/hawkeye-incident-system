"""Unit tests for assemble_timeline (Phase 3.5)."""

from app.constants import IncidentEventType, IncidentStatus, Roles
from app.extensions import db
from app.models.authority import Authority
from app.models.department_action_log import DepartmentActionLog
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent
from app.models.incident_update import IncidentUpdate
from app.services.auth_service import auth_service
from app.services.incident_service import incident_service


def test_assemble_timeline_returns_ordered_events_with_expected_kinds(app):
    """assemble_timeline returns ordered events with expected kind values."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="timeline@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        incident = Incident(
            reported_by_id=user.id,
            title="Test",
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

        # Add a status update
        update = IncidentUpdate(
            incident_id=incident_id,
            updated_by_id=user.id,
            from_status=IncidentStatus.REPORTED.value,
            to_status=IncidentStatus.IN_PROGRESS.value,
            note="Work started",
        )
        db.session.add(update)
        db.session.commit()

        timeline = incident_service.assemble_timeline(incident_id)
        assert len(timeline) >= 2
        kinds = [e.kind for e in timeline]
        assert "incident_created" in kinds
        assert "status_update" in kinds
        # Sorted by at
        for i in range(1, len(timeline)):
            assert timeline[i].at >= timeline[i - 1].at


def test_assemble_timeline_includes_department_action(app):
    """assemble_timeline includes department_action events from DepartmentActionLog."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Auth User",
            email="timeline-auth@example.com",
            password="pass",
            role=Roles.AUTHORITY.value,
        )
        auth = Authority(name="Dept", is_active=True)
        db.session.add(auth)
        db.session.commit()

        incident = Incident(
            reported_by_id=user.id,
            title="Test",
            description="Desc",
            category="Cat",
            suburb_or_ward="Sub",
            street_or_landmark="St",
            location="St, Sub",
            severity="low",
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-000002",
            current_authority_id=auth.id,
        )
        db.session.add(incident)
        db.session.commit()
        incident_id = incident.id

        log = DepartmentActionLog(
            incident_id=incident_id,
            authority_id=auth.id,
            performed_by_id=user.id,
            action_type="site_visit",
            note="Inspected",
        )
        db.session.add(log)
        db.session.commit()

        timeline = incident_service.assemble_timeline(incident_id)
        dept_events = [e for e in timeline if e.kind == "department_action"]
        assert len(dept_events) == 1
        assert "site" in dept_events[0].title.lower() or "visit" in dept_events[0].title.lower()
        assert "Inspected" in dept_events[0].description


def test_assemble_timeline_uses_incident_events_when_present(app):
    """When incident_events exist, timeline is built from them (not synthetic)."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="timeline-events@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        incident = Incident(
            reported_by_id=user.id,
            title="Events Test",
            description="Desc",
            category="Cat",
            suburb_or_ward="Sub",
            street_or_landmark="St",
            location="St, Sub",
            severity="low",
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-000099",
        )
        db.session.add(incident)
        db.session.commit()
        incident_id = incident.id

        # Add incident_events (simulates canonical workflow)
        ev1 = IncidentEvent(
            incident_id=incident_id,
            event_type=IncidentEventType.INCIDENT_CREATED.value,
            to_status=IncidentStatus.REPORTED.value,
            actor_user_id=user.id,
            actor_role="resident",
            note="Incident created",
        )
        db.session.add(ev1)
        ev2 = IncidentEvent(
            incident_id=incident_id,
            event_type=IncidentEventType.STATUS_CHANGED.value,
            from_status=IncidentStatus.REPORTED.value,
            to_status=IncidentStatus.IN_PROGRESS.value,
            actor_user_id=user.id,
            note="Work started",
        )
        db.session.add(ev2)
        db.session.commit()

        timeline = incident_service.assemble_timeline(incident_id)
        kinds = [e.kind for e in timeline]
        assert "incident_created" in kinds
        assert "status_update" in kinds
        # No synthetic incident_created; we have real events
        created_events = [e for e in timeline if e.kind == "incident_created"]
        assert len(created_events) == 1
        assert "Work started" in [e.description for e in timeline if e.kind == "status_update"][0]


def test_assemble_timeline_returns_empty_for_missing_incident(app):
    """assemble_timeline returns empty list for non-existent incident."""
    with app.app_context():
        timeline = incident_service.assemble_timeline(99999)
        assert timeline == []


def test_resident_detail_page_includes_timeline_content(app, client):
    """Resident incident detail page includes timeline content."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="timeline-res@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        incident = Incident(
            reported_by_id=user.id,
            title="Timeline Test",
            description="Desc",
            category="Cat",
            suburb_or_ward="Sub",
            street_or_landmark="St",
            location="St, Sub",
            severity="low",
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-000010",
        )
        db.session.add(incident)
        db.session.commit()
        incident_id = incident.id

    client.post(
        "/auth/login",
        data={"email": "timeline-res@example.com", "password": "pass"},
        follow_redirects=True,
    )
    resp = client.get(f"/resident/incidents/{incident_id}")
    assert resp.status_code == 200
    assert b"Timeline" in resp.data
    assert b"Incident reported" in resp.data or b"reported" in resp.data.lower()


def test_admin_detail_page_includes_timeline_content(app, client):
    """Admin incident detail page includes timeline content."""
    with app.app_context():
        admin, _ = auth_service.register_user(
            name="Admin",
            email="timeline-admin@example.com",
            password="pass",
            role="admin",
        )
        user, _ = auth_service.register_user(
            name="Resident",
            email="timeline-res2@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        incident = Incident(
            reported_by_id=user.id,
            title="Admin Timeline Test",
            description="Desc",
            category="Cat",
            suburb_or_ward="Sub",
            street_or_landmark="St",
            location="St, Sub",
            severity="low",
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-000011",
        )
        db.session.add(incident)
        db.session.commit()
        incident_id = incident.id

    client.post(
        "/auth/login",
        data={"email": "timeline-admin@example.com", "password": "pass"},
        follow_redirects=True,
    )
    resp = client.get(f"/admin/incidents/{incident_id}")
    assert resp.status_code == 200
    assert b"Timeline" in resp.data
    assert b"Incident reported" in resp.data or b"reported" in resp.data.lower()
