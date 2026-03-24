from datetime import timedelta

from app.constants import IncidentStatus, Roles
from app.extensions import db
from app.models import Authority, Incident, IncidentAssignment, IncidentDispatch
from app.services.auth_service import auth_service
from app.utils.datetime_helpers import utc_now


def _seed_escalation_candidate():
    admin, _ = auth_service.register_user(
        name="Admin Esc View",
        email="admin-esc-view@example.com",
        password="password123",
        role=Roles.ADMIN.value,
    )
    resident, _ = auth_service.register_user(
        name="Resident Esc View",
        email="resident-esc-view@example.com",
        password="password123",
        role=Roles.RESIDENT.value,
    )
    authority = Authority(name="Esc Dept", code="ESC_VIEW", is_active=True)
    db.session.add(authority)
    db.session.flush()
    incident = Incident(
        reported_by_id=resident.id,
        title="Esc candidate",
        description="Desc",
        category="cat",
        suburb_or_ward="Ward",
        street_or_landmark="Street",
        location="Street, Ward",
        severity="high",
        status=IncidentStatus.ASSIGNED.value,
        reference_code="HK-2026-03-909090",
        current_authority_id=authority.id,
    )
    db.session.add(incident)
    db.session.flush()
    assignment = IncidentAssignment(
        incident_id=incident.id,
        authority_id=authority.id,
        assigned_by_user_id=admin.id,
    )
    db.session.add(assignment)
    db.session.flush()
    old = utc_now() - timedelta(hours=2)
    dispatch = IncidentDispatch(
        incident_assignment_id=assignment.id,
        incident_id=incident.id,
        authority_id=authority.id,
        dispatched_by_type="admin",
        dispatched_by_id=admin.id,
        dispatch_method="email",
        status="sent",
        ack_status="pending",
        delivery_status="sent",
        dispatched_at=old,
        last_status_update_at=old,
    )
    db.session.add(dispatch)
    # Also seed a non-failed row to verify quick filters.
    second = IncidentDispatch(
        incident_assignment_id=assignment.id,
        incident_id=incident.id,
        authority_id=authority.id,
        dispatched_by_type="admin",
        dispatched_by_id=admin.id,
        dispatch_method="email",
        status="pending",
        ack_status="pending",
        delivery_status="pending",
        dispatched_at=old,
        last_status_update_at=old,
        reminder_count=2,
    )
    db.session.add(second)
    db.session.commit()


def test_admin_escalation_dashboard_renders_candidates(app, client):
    with app.app_context():
        _seed_escalation_candidate()

    client.post(
        "/auth/login",
        data={"email": "admin-esc-view@example.com", "password": "password123"},
        follow_redirects=True,
    )
    resp = client.get("/admin/escalations")
    assert resp.status_code == 200
    assert b"Escalation Dashboard" in resp.data
    assert b"Escalate now" in resp.data
    assert b"HK-2026-03-909090" in resp.data
    assert b"Pending" in resp.data
    assert b"Sent" in resp.data
    assert b"Failed" in resp.data
    assert b"Open incident" in resp.data


def test_admin_escalation_dashboard_quick_filters(app, client):
    with app.app_context():
        _seed_escalation_candidate()

    client.post(
        "/auth/login",
        data={"email": "admin-esc-view@example.com", "password": "password123"},
        follow_redirects=True,
    )
    failed_only = client.get("/admin/escalations?status=failed")
    assert failed_only.status_code == 200
    assert b"Failed" in failed_only.data

    min_reminders = client.get("/admin/escalations?min_reminders=2")
    assert min_reminders.status_code == 200
    assert b"Pending" in min_reminders.data
