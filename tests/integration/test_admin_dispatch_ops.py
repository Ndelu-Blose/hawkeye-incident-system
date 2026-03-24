from app.constants import IncidentStatus, Roles
from app.extensions import db
from app.models import Authority, DepartmentContact, Incident, IncidentAssignment, IncidentDispatch
from app.services.auth_service import auth_service


def _seed_admin_dispatch_incident():
    admin, _ = auth_service.register_user(
        name="Admin Dispatch Ops",
        email="admin-dispatch-ops@example.com",
        password="password123",
        role=Roles.ADMIN.value,
    )
    resident, _ = auth_service.register_user(
        name="Resident Dispatch Ops",
        email="resident-dispatch-ops@example.com",
        password="password123",
        role=Roles.RESIDENT.value,
    )
    authority = Authority(
        name="Metro Police",
        code="METRO_POLICE",
        is_active=True,
        routing_enabled=True,
        notifications_enabled=True,
    )
    db.session.add(authority)
    db.session.flush()
    incident = Incident(
        reported_by_id=resident.id,
        title="Dispatch ops test",
        description="Desc",
        category="suspicious_activity",
        suburb_or_ward="Ward 12",
        street_or_landmark="Gate Drive",
        location="Gate Drive, Ward 12",
        severity="high",
        status=IncidentStatus.ASSIGNED.value,
        reference_code="HK-2026-03-777777",
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
        status="failed",
        delivery_status="failed",
        ack_status="pending",
        failure_reason="smtp timeout",
    )
    db.session.add(dispatch)
    db.session.commit()
    return incident.id, dispatch.id, authority.id


def test_admin_can_retry_dispatch(app, client, monkeypatch):
    with app.app_context():
        incident_id, dispatch_id, authority_id = _seed_admin_dispatch_incident()
        db.session.add(
            DepartmentContact(
                authority_id=authority_id,
                contact_type="primary",
                channel="email",
                value="metro@example.com",
                is_active=True,
            )
        )
        db.session.commit()

    client.post(
        "/auth/login",
        data={"email": "admin-dispatch-ops@example.com", "password": "password123"},
        follow_redirects=True,
    )
    monkeypatch.setattr("app.services.dispatch_service.mail.send", lambda msg: None)

    resp = client.post(
        f"/admin/incidents/{incident_id}/dispatch/{dispatch_id}/retry",
        data={},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        dispatch = db.session.get(IncidentDispatch, dispatch_id)
        assert dispatch is not None
        assert dispatch.status == "sent"
        assert dispatch.delivery_status == "sent"
        assert dispatch.recipient_email == "metro@example.com"


def test_admin_can_save_external_reference(app, client):
    with app.app_context():
        incident_id, dispatch_id, _ = _seed_admin_dispatch_incident()

    client.post(
        "/auth/login",
        data={"email": "admin-dispatch-ops@example.com", "password": "password123"},
        follow_redirects=True,
    )
    resp = client.post(
        f"/admin/incidents/{incident_id}/dispatch/{dispatch_id}/external-reference",
        data={
            "external_reference_number": "ETH-FAULT-88214",
            "external_reference_source": "eThekwini",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        dispatch = db.session.get(IncidentDispatch, dispatch_id)
        assert dispatch is not None
        assert dispatch.external_reference_number == "ETH-FAULT-88214"
        assert dispatch.external_reference_source == "eThekwini"


def test_admin_can_auto_generate_external_reference_when_blank(app, client):
    with app.app_context():
        incident_id, dispatch_id, authority_id = _seed_admin_dispatch_incident()
        authority = db.session.get(Authority, authority_id)
        assert authority is not None
        authority.code = "METRO_POLICE"
        db.session.commit()

    client.post(
        "/auth/login",
        data={"email": "admin-dispatch-ops@example.com", "password": "password123"},
        follow_redirects=True,
    )
    resp = client.post(
        f"/admin/incidents/{incident_id}/dispatch/{dispatch_id}/external-reference",
        data={
            "external_reference_number": "",
            "external_reference_source": "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        dispatch = db.session.get(IncidentDispatch, dispatch_id)
        assert dispatch is not None
        assert dispatch.external_reference_number is not None
        assert dispatch.external_reference_number.startswith("HK-METRO-POLICE-")
        assert f"-{incident_id:04d}-{dispatch_id:04d}" in dispatch.external_reference_number
        assert dispatch.external_reference_source == "Metro Police"
