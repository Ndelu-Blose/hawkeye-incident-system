"""Unit tests for dispatch log lifecycle helpers."""

from app.constants import IncidentStatus, Roles
from app.extensions import db
from app.models import Authority, Incident, IncidentAssignment
from app.services.auth_service import auth_service
from app.services.incident_service import incident_service


def _seed_incident_context():
    resident, _ = auth_service.register_user(
        name="Dispatch Resident",
        email="dispatch-log-resident@example.com",
        password="pass",
        role=Roles.RESIDENT.value,
    )
    admin, _ = auth_service.register_user(
        name="Dispatch Admin",
        email="dispatch-log-admin@example.com",
        password="pass",
        role=Roles.ADMIN.value,
    )
    authority = Authority(name="Ops Dept", is_active=True)
    db.session.add(authority)
    db.session.flush()
    incident = Incident(
        reported_by_id=resident.id,
        title="Dispatch log test",
        description="Desc",
        category="Cat",
        suburb_or_ward="Sub",
        street_or_landmark="Street",
        location="Street, Sub",
        severity="high",
        status=IncidentStatus.ASSIGNED.value,
        current_authority_id=authority.id,
        reference_code="HK-2026-03-111111",
    )
    db.session.add(incident)
    db.session.flush()
    assignment = IncidentAssignment(
        incident_id=incident.id,
        authority_id=authority.id,
        assigned_by_user_id=admin.id,
    )
    db.session.add(assignment)
    db.session.commit()
    return resident, admin, authority, incident, assignment


def test_dispatch_log_create_and_status_lifecycle(app):
    with app.app_context():
        resident, admin, authority, incident, assignment = _seed_incident_context()
        dispatch = incident_service.create_dispatch(
            incident_id=incident.id,
            authority_id=authority.id,
            incident_assignment_id=assignment.id,
            channel="email",
            recipient_email="ops@example.com",
            subject_snapshot="Dispatch subject",
            message_snapshot="Dispatch body",
            created_by_user_id=admin.id,
            dispatched_by_type="admin",
        )
        incident_service.mark_sent(
            dispatch,
            delivery_provider="smtp",
            delivery_reference="smtp-msg-1",
        )
        incident_service.mark_acknowledged(
            dispatch, actor_user=resident, acknowledged_by="Ops Agent"
        )
        incident_service.mark_resolved(
            dispatch,
            resolution_note="Issue fixed",
            resolution_proof_url="https://example.com/proof.jpg",
        )
        db.session.commit()

        assert dispatch.status == "resolved"
        assert dispatch.channel == "email"
        assert dispatch.recipient_email == "ops@example.com"
        assert dispatch.subject_snapshot == "Dispatch subject"
        assert dispatch.message_snapshot == "Dispatch body"
        assert dispatch.delivery_provider == "smtp"
        assert dispatch.delivery_reference == "smtp-msg-1"
        assert dispatch.ack_status == "acknowledged"
        assert dispatch.acknowledged_by == "Ops Agent"
        assert dispatch.sent_at is not None
        assert dispatch.acknowledged_at is not None
        assert dispatch.resolved_at is not None
        assert dispatch.last_status_update_at is not None


def test_dispatch_log_external_reference_and_timeline_visibility(app):
    with app.app_context():
        _, admin, authority, incident, assignment = _seed_incident_context()
        dispatch = incident_service.create_dispatch(
            incident_id=incident.id,
            authority_id=authority.id,
            incident_assignment_id=assignment.id,
            channel="manual",
            created_by_user_id=admin.id,
            dispatched_by_type="admin",
        )
        incident_service.attach_external_reference(
            dispatch,
            reference_number="ETH-FAULT-88214",
            source="eThekwini",
        )
        db.session.commit()

        timeline = incident_service.assemble_timeline(incident.id)
        dispatch_events = [e for e in timeline if e.kind == "dispatched"]
        assert dispatch.external_reference_number == "ETH-FAULT-88214"
        assert dispatch.external_reference_source == "eThekwini"
        assert dispatch_events
        assert any("ETH-FAULT-88214" in (e.description or "") for e in dispatch_events)
