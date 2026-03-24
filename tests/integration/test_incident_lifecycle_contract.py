"""Contract tests: valid transitions write exactly one incident_events row."""

from app.constants import IncidentEventType, IncidentStatus, Roles
from app.extensions import db
from app.models import Authority, IncidentAssignment, IncidentDispatch
from app.models.authority_user import AuthorityUser
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent
from app.models.user import User
from app.services.auth_service import auth_service
from app.services.incident_service import incident_service


def _event_count(incident_id: int) -> int:
    return len(incident_service.event_repo.list_for_incident(incident_id))


def _latest_event(incident_id: int) -> IncidentEvent | None:
    events = incident_service.event_repo.list_for_incident(incident_id)
    return events[-1] if events else None


def _make_incident(app, status: IncidentStatus = IncidentStatus.REPORTED) -> tuple[Incident, int]:
    """Create resident, admin, incident. Caller must be in app_context. Return (incident, admin_id)."""
    resident, _ = auth_service.register_user(
        name="Resident",
        email="lifecycle-res@example.com",
        password="pass",
        role=Roles.RESIDENT.value,
    )
    admin, _ = auth_service.register_user(
        name="Admin",
        email="lifecycle-admin@example.com",
        password="pass",
        role=Roles.ADMIN.value,
    )
    incident = Incident(
        reported_by_id=resident.id,
        title="Test",
        description="Desc",
        category="Cat",
        suburb_or_ward="Sub",
        street_or_landmark="St",
        location="St, Sub",
        severity="low",
        status=status.value,
        reference_code="HK-2026-03-000001",
    )
    db.session.add(incident)
    db.session.commit()
    incident_id = incident.id
    # Add incident_created event if not already present (for direct-created incidents)
    if _event_count(incident_id) == 0:
        incident_service.event_repo.create(
            incident_id=incident_id,
            event_type=IncidentEventType.INCIDENT_CREATED.value,
            to_status=IncidentStatus.REPORTED.value,
            actor_user_id=resident.id,
            actor_role="resident",
        )
        db.session.commit()
    return incident, admin.id


def test_reported_to_screened_writes_one_event(app):
    """reported -> screened writes exactly one incident_screened event."""
    with app.app_context():
        incident, admin_id = _make_incident(app)
        admin_user = db.session.get(User, admin_id)
        before = _event_count(incident.id)

        ok, errors = incident_service.update_status(
            incident.id,
            IncidentStatus.SCREENED,
            note="Screened",
            authority_user=admin_user,
            allow_admin_override=True,
        )
        assert ok, errors
        db.session.commit()

        after = _event_count(incident.id)
        assert after == before + 1
        ev = _latest_event(incident.id)
        assert ev.event_type == IncidentEventType.INCIDENT_SCREENED.value
        assert ev.from_status == IncidentStatus.REPORTED.value
        assert ev.to_status == IncidentStatus.SCREENED.value


def test_screened_to_assigned_writes_one_event(app):
    """screened -> assigned writes exactly one incident_assigned event."""
    with app.app_context():
        incident, admin_id = _make_incident(app, IncidentStatus.SCREENED)
        auth = Authority(name="Dept", is_active=True)
        db.session.add(auth)
        db.session.commit()

        before = _event_count(incident.id)

        ok, errors = incident_service.change_status(
            incident,
            IncidentStatus.ASSIGNED,
            actor_user_id=admin_id,
            actor_role="admin",
            authority_id=auth.id,
        )
        assert ok, errors
        db.session.commit()

        after = _event_count(incident.id)
        assert after == before + 1
        ev = _latest_event(incident.id)
        assert ev.event_type == IncidentEventType.INCIDENT_ASSIGNED.value
        assert ev.from_status == IncidentStatus.SCREENED.value
        assert ev.to_status == IncidentStatus.ASSIGNED.value


def test_assigned_to_acknowledged_via_dispatch_writes_event(app):
    """assigned -> acknowledged (via acknowledge_dispatch) writes incident_acknowledged event."""
    with app.app_context():
        incident, admin_id = _make_incident(app, IncidentStatus.ASSIGNED)
        auth = Authority(name="Dept", is_active=True)
        db.session.add(auth)
        db.session.commit()

        assignment = IncidentAssignment(
            incident_id=incident.id,
            authority_id=auth.id,
            assigned_by_user_id=admin_id,
        )
        db.session.add(assignment)
        db.session.flush()
        dispatch = IncidentDispatch(
            incident_assignment_id=assignment.id,
            incident_id=incident.id,
            authority_id=auth.id,
            dispatched_by_type="admin",
            dispatched_by_id=admin_id,
            ack_status="pending",
        )
        db.session.add(dispatch)
        db.session.commit()

        auth_user, _ = auth_service.register_user(
            name="Dept User",
            email="lifecycle-dept@example.com",
            password="pass",
            role=Roles.AUTHORITY.value,
        )
        db.session.add(AuthorityUser(user_id=auth_user.id, authority_id=auth.id))
        db.session.commit()

        before = _event_count(incident.id)

        ok, errors = incident_service.acknowledge_dispatch(
            dispatch.id, auth_user, note="Acknowledged"
        )
        assert ok, errors

        after = _event_count(incident.id)
        assert after == before + 2  # incident_acknowledged event + status_changed
        events = incident_service.event_repo.list_for_incident(incident.id)
        ack_events = [
            e for e in events if e.event_type == IncidentEventType.INCIDENT_ACKNOWLEDGED.value
        ]
        assert len(ack_events) >= 1


def test_acknowledged_to_in_progress_writes_one_event(app):
    """acknowledged -> in_progress writes exactly one status_changed event."""
    with app.app_context():
        incident, admin_id = _make_incident(app, IncidentStatus.ACKNOWLEDGED)
        admin_user = db.session.get(User, admin_id)
        before = _event_count(incident.id)

        ok, errors = incident_service.update_status(
            incident.id,
            IncidentStatus.IN_PROGRESS,
            note="Work started",
            authority_user=admin_user,
        )
        assert ok, errors
        db.session.commit()

        after = _event_count(incident.id)
        assert after == before + 1
        ev = _latest_event(incident.id)
        assert ev.event_type == IncidentEventType.STATUS_CHANGED.value
        assert ev.to_status == IncidentStatus.IN_PROGRESS.value


def test_in_progress_to_resolved_writes_one_event(app):
    """in_progress -> resolved writes exactly one incident_resolved event."""
    with app.app_context():
        incident, admin_id = _make_incident(app, IncidentStatus.IN_PROGRESS)
        admin_user = db.session.get(User, admin_id)
        before = _event_count(incident.id)

        ok, errors = incident_service.update_status(
            incident.id,
            IncidentStatus.RESOLVED,
            note="Fixed",
            authority_user=admin_user,
        )
        assert ok, errors
        db.session.commit()

        after = _event_count(incident.id)
        assert after == before + 1
        ev = _latest_event(incident.id)
        assert ev.event_type == IncidentEventType.INCIDENT_RESOLVED.value
        assert ev.to_status == IncidentStatus.RESOLVED.value


def test_resolved_to_closed_writes_one_event(app):
    """resolved -> closed writes exactly one incident_closed event."""
    with app.app_context():
        incident, admin_id = _make_incident(app, IncidentStatus.RESOLVED)
        admin_user = db.session.get(User, admin_id)
        before = _event_count(incident.id)

        ok, errors = incident_service.update_status(
            incident.id,
            IncidentStatus.CLOSED,
            note="Closed",
            authority_user=admin_user,
        )
        assert ok, errors
        db.session.commit()

        after = _event_count(incident.id)
        assert after == before + 1
        ev = _latest_event(incident.id)
        assert ev.event_type == IncidentEventType.INCIDENT_CLOSED.value
        assert ev.to_status == IncidentStatus.CLOSED.value


def test_invalid_transition_fails(app):
    """Invalid transition (e.g. reported -> closed) fails."""
    with app.app_context():
        incident, admin_id = _make_incident(app)
        admin_user = db.session.get(User, admin_id)
        before = _event_count(incident.id)

        ok, errors = incident_service.update_status(
            incident.id,
            IncidentStatus.CLOSED,
            note="",
            authority_user=admin_user,
            allow_admin_override=False,
        )
        assert not ok
        assert "Invalid status transition" in str(errors)

        after = _event_count(incident.id)
        assert after == before  # no new event
