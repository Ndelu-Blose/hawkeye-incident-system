"""Unit tests for IncidentDispatch and DepartmentActionLog (Phase 3.5)."""

import io

from werkzeug.datastructures import FileStorage

from app.constants import Roles
from app.extensions import db
from app.models.authority import Authority
from app.models.department_action_log import DepartmentActionLog
from app.models.incident_assignment import IncidentAssignment
from app.models.incident_category import IncidentCategory
from app.models.incident_dispatch import IncidentDispatch
from app.models.routing_rule import RoutingRule
from app.services.auth_service import auth_service
from app.services.incident_service import incident_service
from tests.conftest import MINIMAL_PNG_BYTES


def test_auto_routed_incident_creates_assignment_and_dispatch(app):
    """Auto-routed incident creation yields one IncidentAssignment and one IncidentDispatch."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="dispatch@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        cat = IncidentCategory(
            name="water_leak",
            description="Water leak",
            is_active=True,
        )
        auth = Authority(name="Water Dept", is_active=True)
        db.session.add_all([cat, auth])
        db.session.commit()

        rule = RoutingRule(
            category_id=cat.id,
            authority_id=auth.id,
            is_active=True,
        )
        db.session.add(rule)
        db.session.commit()

        payload = {
            "category_id": str(cat.id),
            "category": "water_leak",
            "title": "Leak in street",
            "description": "Water leaking",
            "suburb_or_ward": "North",
            "street_or_landmark": "Main St",
            "severity": "medium",
        }
        files = [FileStorage(stream=io.BytesIO(MINIMAL_PNG_BYTES), filename="e.png")]
        incident, errors = incident_service.create_incident(payload, user, files=files)
        assert incident is not None
        assert not errors

        assignments = list(
            db.session.query(IncidentAssignment).filter(
                IncidentAssignment.incident_id == incident.id
            )
        )
        assert len(assignments) == 1
        assignment = assignments[0]
        assert assignment.authority_id == auth.id
        assert assignment.incident_id == incident.id

        dispatches = list(
            db.session.query(IncidentDispatch).filter(IncidentDispatch.incident_id == incident.id)
        )
        assert len(dispatches) == 1
        dispatch = dispatches[0]
        assert dispatch.incident_assignment_id == assignment.id
        assert dispatch.incident_id == incident.id
        assert dispatch.authority_id == auth.id
        assert dispatch.dispatch_method == "internal_queue"
        assert dispatch.dispatched_by_type == "system"
        assert dispatch.delivery_status == "pending"
        assert dispatch.ack_status == "pending"


def test_log_department_action_persists_row(app):
    """log_department_action creates and persists the expected DepartmentActionLog row."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Authority User",
            email="auth@example.com",
            password="pass",
            role=Roles.AUTHORITY.value,
        )
        auth = Authority(name="Test Dept", is_active=True)
        db.session.add(auth)
        db.session.commit()

        from app.models.incident import Incident

        incident = Incident(
            reported_by_id=user.id,
            title="Test",
            description="Desc",
            category="Cat",
            suburb_or_ward="Sub",
            street_or_landmark="St",
            location="St, Sub",
            severity="low",
            status="reported",
            reference_code="HK-2026-03-000099",
            current_authority_id=auth.id,
        )
        db.session.add(incident)
        db.session.commit()
        incident_id = incident.id
        authority_id = auth.id

        log = incident_service.log_department_action(
            incident_id=incident_id,
            authority_id=authority_id,
            performed_by=user,
            action_type="site_visit",
            note="Inspected the site",
        )
        assert log is not None
        assert log.incident_id == incident_id
        assert log.authority_id == authority_id
        assert log.performed_by_id == user.id
        assert log.action_type == "site_visit"
        assert log.note == "Inspected the site"

        persisted = (
            db.session.query(DepartmentActionLog)
            .filter(DepartmentActionLog.incident_id == incident_id)
            .first()
        )
        assert persisted is not None
        assert persisted.action_type == "site_visit"
        assert persisted.note == "Inspected the site"


def test_log_department_action_returns_none_for_missing_incident(app):
    """log_department_action returns None when incident does not exist."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Auth",
            email="auth2@example.com",
            password="pass",
            role=Roles.AUTHORITY.value,
        )
        auth = Authority(name="Dept", is_active=True)
        db.session.add(auth)
        db.session.commit()

        log = incident_service.log_department_action(
            incident_id=99999,
            authority_id=auth.id,
            performed_by=user,
            action_type="note",
            note="Test",
        )
        assert log is None
