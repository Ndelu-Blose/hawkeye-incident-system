from app.constants import IncidentStatus, Roles
from app.extensions import db
from app.models import Authority, DepartmentContact, Incident, IncidentAssignment, IncidentDispatch
from app.services.auth_service import auth_service
from app.services.dispatch_service import dispatch_service


def _seed_dispatch_context():
    resident, _ = auth_service.register_user(
        name="Resident",
        email="dispatch-svc-res@example.com",
        password="pass",
        role=Roles.RESIDENT.value,
    )
    admin, _ = auth_service.register_user(
        name="Admin",
        email="dispatch-svc-admin@example.com",
        password="pass",
        role=Roles.ADMIN.value,
    )
    authority = Authority(
        name="Water and Sanitation",
        code="WATER_SANITATION",
        is_active=True,
        routing_enabled=True,
        notifications_enabled=True,
    )
    db.session.add(authority)
    db.session.flush()
    incident = Incident(
        reported_by_id=resident.id,
        title="Leak",
        description="Water leak in road",
        category="water_leak",
        suburb_or_ward="Ward 10",
        street_or_landmark="Main Street",
        location="Main Street, Ward 10",
        severity="high",
        status=IncidentStatus.ASSIGNED.value,
        reference_code="HK-2026-03-123456",
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
    dispatch = IncidentDispatch(
        incident_assignment_id=assignment.id,
        incident_id=incident.id,
        authority_id=authority.id,
        dispatch_method="email",
        dispatched_by_type="admin",
        dispatched_by_id=admin.id,
        status="pending",
        ack_status="pending",
        delivery_status="pending",
    )
    db.session.add(dispatch)
    db.session.commit()
    return authority, dispatch


def test_resolve_primary_email_prefers_verified_primary_then_secondary(app):
    with app.app_context():
        authority, _ = _seed_dispatch_context()
        db.session.add(
            DepartmentContact(
                authority_id=authority.id,
                contact_type="secondary",
                is_primary=False,
                is_secondary=True,
                channel="email",
                value="verified-secondary@example.com",
                is_active=True,
                verification_status="verified",
            )
        )
        db.session.add(
            DepartmentContact(
                authority_id=authority.id,
                contact_type="primary",
                is_primary=True,
                is_secondary=False,
                channel="email",
                value="unverified-primary@example.com",
                is_active=True,
                verification_status="unverified",
            )
        )
        db.session.add(
            DepartmentContact(
                authority_id=authority.id,
                contact_type="primary",
                is_primary=True,
                is_secondary=False,
                channel="email",
                value="verified-primary@example.com",
                is_active=True,
                verification_status="verified",
            )
        )
        db.session.commit()
        resolved = dispatch_service.resolve_primary_email(authority)
        assert resolved == "verified-primary@example.com"


def test_send_assignment_dispatch_records_snapshots_and_status(app, monkeypatch):
    with app.app_context():
        authority, dispatch = _seed_dispatch_context()
        db.session.add(
            DepartmentContact(
                authority_id=authority.id,
                contact_type="primary",
                channel="email",
                value="ops@example.com",
                is_active=True,
            )
        )
        db.session.commit()

        monkeypatch.setattr("app.services.dispatch_service.mail.send", lambda msg: None)
        result = dispatch_service.send_assignment_dispatch(dispatch)
        db.session.commit()

        assert result.ok is True
        assert dispatch.status == "sent"
        assert dispatch.delivery_status == "sent"
        assert dispatch.recipient_email == "ops@example.com"
        assert "Alertweb Dispatch" in (dispatch.subject_snapshot or "")
        assert "Action Required" in (dispatch.message_snapshot or "")


def test_send_assignment_dispatch_fails_without_email_contact(app):
    with app.app_context():
        _, dispatch = _seed_dispatch_context()
        result = dispatch_service.send_assignment_dispatch(dispatch)
        db.session.commit()
        assert result.ok is False
        assert dispatch.status == "failed"
        assert "No dispatchable email contact" in (dispatch.failure_reason or "")
