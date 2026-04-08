"""Authority incident UI: workflow actions replace free status dropdown."""

from __future__ import annotations

from app.constants import IncidentStatus, Roles
from app.extensions import db
from app.models.authority import Authority
from app.models.authority_user import AuthorityUser
from app.models.incident import Incident
from app.models.incident_assignment import IncidentAssignment
from app.models.incident_dispatch import IncidentDispatch
from app.services.auth_service import auth_service
from app.utils.datetime_helpers import utc_now


def _seed_assigned_incident(app):
    with app.app_context():
        resident, _ = auth_service.register_user(
            name="Res R",
            email="resident.r@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        dept_user, _ = auth_service.register_user(
            name="Dept U",
            email="dept.u@example.com",
            password="pass",
            role=Roles.AUTHORITY.value,
        )
        authority = Authority(name="Test Dept", contact_email="dept@example.com", is_active=True)
        db.session.add(authority)
        db.session.flush()
        db.session.add(AuthorityUser(authority_id=authority.id, user_id=dept_user.id))
        incident = Incident(
            reported_by_id=resident.id,
            title="Case",
            description="Desc",
            category="crime",
            suburb_or_ward="W1",
            street_or_landmark="St",
            location="St, W1",
            severity="medium",
            status=IncidentStatus.ASSIGNED.value,
            reference_code="HK-TEST-AUTH-001",
            current_authority_id=authority.id,
        )
        db.session.add(incident)
        db.session.flush()
        assignment = IncidentAssignment(
            incident_id=incident.id,
            authority_id=authority.id,
            assigned_by_user_id=dept_user.id,
        )
        db.session.add(assignment)
        db.session.flush()
        dispatch = IncidentDispatch(
            incident_assignment_id=assignment.id,
            incident_id=incident.id,
            authority_id=authority.id,
            dispatch_method="email",
            dispatched_by_type="admin",
            dispatched_by_id=dept_user.id,
            status="sent",
            delivery_status="sent",
            ack_status="pending",
            recipient_email="dept@example.com",
            last_status_update_at=utc_now(),
        )
        db.session.add(dispatch)
        db.session.commit()
        return incident.id, dept_user.id


def test_authority_cannot_set_status_via_freeform_screened(app, client):
    incident_id, _ = _seed_assigned_incident(app)

    client.post(
        "/auth/login",
        data={"email": "dept.u@example.com", "password": "pass"},
        follow_redirects=True,
    )
    resp = client.post(
        f"/authority/incidents/{incident_id}/status",
        data={"status": "screened", "note": "oops"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        incident = db.session.get(Incident, incident_id)
        assert incident is not None
        assert incident.status == IncidentStatus.ASSIGNED.value


def test_authority_reject_from_assigned_with_note(app, client):
    incident_id, _ = _seed_assigned_incident(app)

    client.post(
        "/auth/login",
        data={"email": "dept.u@example.com", "password": "pass"},
        follow_redirects=True,
    )
    resp = client.post(
        f"/authority/incidents/{incident_id}/status",
        data={"status": "rejected", "note": "Outside our jurisdiction."},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        incident = db.session.get(Incident, incident_id)
        assert incident is not None
        assert incident.status == IncidentStatus.REJECTED.value


def test_authority_cannot_acknowledge_via_status_post(app, client):
    """Acknowledged must use /acknowledge, not the status form."""
    incident_id, _ = _seed_assigned_incident(app)

    client.post(
        "/auth/login",
        data={"email": "dept.u@example.com", "password": "pass"},
        follow_redirects=True,
    )
    resp = client.post(
        f"/authority/incidents/{incident_id}/status",
        data={"status": "acknowledged", "note": "Trying to skip dispatch"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        incident = db.session.get(Incident, incident_id)
        assert incident is not None
        assert incident.status == IncidentStatus.ASSIGNED.value
