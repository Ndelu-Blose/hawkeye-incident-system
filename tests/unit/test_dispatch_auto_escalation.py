from datetime import timedelta

from app.constants import IncidentStatus, Roles
from app.extensions import db
from app.models import Authority, DepartmentContact, Incident, IncidentAssignment, IncidentDispatch
from app.services.auth_service import auth_service
from app.services.dispatch_service import dispatch_service
from app.utils.datetime_helpers import utc_now


def _seed_escalation_dispatch(*, status: str = "sent", reminder_count: int = 0):
    resident, _ = auth_service.register_user(
        name="Esc Resident",
        email="esc-res@example.com",
        password="pass",
        role=Roles.RESIDENT.value,
    )
    admin, _ = auth_service.register_user(
        name="Esc Admin",
        email="esc-admin@example.com",
        password="pass",
        role=Roles.ADMIN.value,
    )
    authority = Authority(
        name="Esc Dept",
        code="ESC_DEPT",
        is_active=True,
        routing_enabled=True,
        notifications_enabled=True,
    )
    db.session.add(authority)
    db.session.flush()
    db.session.add(
        DepartmentContact(
            authority_id=authority.id,
            contact_type="primary",
            channel="email",
            value="escalation@example.com",
            is_active=True,
        )
    )
    incident = Incident(
        reported_by_id=resident.id,
        title="Escalation test",
        description="Desc",
        category="cat",
        suburb_or_ward="Ward",
        street_or_landmark="Street",
        location="Street, Ward",
        severity="high",
        status=IncidentStatus.ASSIGNED.value,
        reference_code="HK-2026-03-555555",
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
    old = utc_now() - timedelta(hours=3)
    dispatch = IncidentDispatch(
        incident_assignment_id=assignment.id,
        incident_id=incident.id,
        authority_id=authority.id,
        dispatch_method="email",
        dispatched_by_type="admin",
        dispatched_by_id=admin.id,
        status=status,
        delivery_status=status if status in ("sent", "failed") else "pending",
        ack_status="pending",
        dispatched_at=old,
        last_status_update_at=old,
        reminder_count=reminder_count,
    )
    db.session.add(dispatch)
    db.session.commit()
    return dispatch.id


def test_process_auto_escalations_sends_reminder_for_stale_dispatch(app, monkeypatch):
    with app.app_context():
        dispatch_id = _seed_escalation_dispatch(status="sent", reminder_count=0)
        monkeypatch.setattr("app.services.dispatch_service.mail.send", lambda msg: None)
        result = dispatch_service.process_auto_escalations(limit=50)
        dispatch = db.session.get(IncidentDispatch, dispatch_id)
        assert result["processed"] >= 1
        assert result["reminders_sent"] >= 1
        assert dispatch is not None
        assert dispatch.reminder_count >= 1
        assert dispatch.last_reminder_at is not None


def test_process_auto_escalations_respects_max_reminders(app, monkeypatch):
    with app.app_context():
        dispatch_id = _seed_escalation_dispatch(status="failed", reminder_count=3)
        monkeypatch.setattr("app.services.dispatch_service.mail.send", lambda msg: None)
        result = dispatch_service.process_auto_escalations(limit=50)
        dispatch = db.session.get(IncidentDispatch, dispatch_id)
        assert result["processed"] == 0
        assert dispatch is not None
        assert dispatch.reminder_count == 3
