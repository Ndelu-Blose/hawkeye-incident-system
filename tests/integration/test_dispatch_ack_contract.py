"""Contract tests: dispatch acknowledgment updates both dispatch and incident status."""

from app.constants import IncidentEventType, IncidentStatus, Roles
from app.extensions import db
from app.models import Authority, IncidentAssignment, IncidentDispatch
from app.models.authority_user import AuthorityUser
from app.models.incident import Incident
from app.services.auth_service import auth_service
from app.services.incident_service import incident_service


def test_acknowledge_dispatch_updates_dispatch_and_status(app):
    """Acknowledge dispatch: dispatch fields updated, incident status acknowledged, event written."""
    with app.app_context():
        resident, _ = auth_service.register_user(
            name="Resident",
            email="ack-res@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        admin, _ = auth_service.register_user(
            name="Admin",
            email="ack-admin@example.com",
            password="pass",
            role=Roles.ADMIN.value,
        )
        auth = Authority(name="Dept", is_active=True)
        db.session.add(auth)
        db.session.commit()

        incident = Incident(
            reported_by_id=resident.id,
            title="Test",
            description="Desc",
            category="Cat",
            suburb_or_ward="Sub",
            street_or_landmark="St",
            location="St, Sub",
            severity="low",
            status=IncidentStatus.ASSIGNED.value,
            current_authority_id=auth.id,
            reference_code="HK-2026-03-000001",
        )
        db.session.add(incident)
        db.session.commit()

        assignment = IncidentAssignment(
            incident_id=incident.id,
            authority_id=auth.id,
            assigned_by_user_id=admin.id,
        )
        db.session.add(assignment)
        db.session.flush()
        dispatch = IncidentDispatch(
            incident_assignment_id=assignment.id,
            incident_id=incident.id,
            authority_id=auth.id,
            dispatched_by_type="admin",
            dispatched_by_id=admin.id,
            ack_status="pending",
        )
        db.session.add(dispatch)
        db.session.commit()

        auth_user, _ = auth_service.register_user(
            name="Dept User",
            email="ack-dept@example.com",
            password="pass",
            role=Roles.AUTHORITY.value,
        )
        db.session.add(AuthorityUser(user_id=auth_user.id, authority_id=auth.id))
        db.session.commit()

        events_before = len(incident_service.event_repo.list_for_incident(incident.id))

        ok, errors = incident_service.acknowledge_dispatch(dispatch.id, auth_user, note="Received")
        assert ok, errors

        db.session.refresh(dispatch)
        db.session.refresh(incident)

        assert dispatch.ack_status == "acknowledged"
        assert dispatch.ack_user_id == auth_user.id
        assert dispatch.ack_at is not None
        assert incident.status == IncidentStatus.ACKNOWLEDGED.value

        events_after = incident_service.event_repo.list_for_incident(incident.id)
        assert len(events_after) > events_before
        ack_events = [
            e for e in events_after if e.event_type == IncidentEventType.INCIDENT_ACKNOWLEDGED.value
        ]
        assert len(ack_events) >= 1


def test_double_acknowledge_fails(app):
    """Acknowledging an already-acknowledged dispatch fails."""
    with app.app_context():
        resident, _ = auth_service.register_user(
            name="Resident",
            email="ack-res2@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        admin, _ = auth_service.register_user(
            name="Admin",
            email="ack-admin2@example.com",
            password="pass",
            role=Roles.ADMIN.value,
        )
        auth = Authority(name="Dept", is_active=True)
        db.session.add(auth)
        db.session.commit()

        incident = Incident(
            reported_by_id=resident.id,
            title="Test",
            description="Desc",
            category="Cat",
            suburb_or_ward="Sub",
            street_or_landmark="St",
            location="St, Sub",
            severity="low",
            status=IncidentStatus.ASSIGNED.value,
            current_authority_id=auth.id,
            reference_code="HK-2026-03-000002",
        )
        db.session.add(incident)
        db.session.commit()

        assignment = IncidentAssignment(
            incident_id=incident.id,
            authority_id=auth.id,
            assigned_by_user_id=admin.id,
        )
        db.session.add(assignment)
        db.session.flush()
        dispatch = IncidentDispatch(
            incident_assignment_id=assignment.id,
            incident_id=incident.id,
            authority_id=auth.id,
            dispatched_by_type="admin",
            dispatched_by_id=admin.id,
            ack_status="pending",
        )
        db.session.add(dispatch)
        db.session.commit()

        auth_user, _ = auth_service.register_user(
            name="Dept User 2",
            email="ack-dept2@example.com",
            password="pass",
            role=Roles.AUTHORITY.value,
        )
        db.session.add(AuthorityUser(user_id=auth_user.id, authority_id=auth.id))
        db.session.commit()

        ok1, _ = incident_service.acknowledge_dispatch(dispatch.id, auth_user)
        assert ok1

        ok2, errors = incident_service.acknowledge_dispatch(dispatch.id, auth_user)
        assert not ok2
        assert "already acknowledged" in str(errors).lower()
