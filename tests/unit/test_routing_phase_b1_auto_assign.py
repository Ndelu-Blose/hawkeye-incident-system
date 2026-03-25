from __future__ import annotations

import io

from werkzeug.datastructures import FileStorage

from app.constants import IncidentEventType, Roles
from app.extensions import db
from app.models import (
    Authority,
    IncidentAssignment,
    IncidentCategory,
    IncidentDispatch,
    Location,
    RoutingRule,
)
from app.services.auth_service import auth_service
from app.services.incident_service import incident_service
from tests.conftest import MINIMAL_PNG_BYTES


def _payload(*, category_id: int, category: str, location_id: int) -> dict:
    return {
        "category_id": str(category_id),
        "category": category,
        "title": "Water leak reported",
        "description": "There is a water leak in the street",
        "suburb_or_ward": "North",
        "street_or_landmark": "Main St",
        "location_id": str(location_id),
        "severity": "low",
    }


def test_b1_auto_assign_exact_high_confidence_creates_assignment_and_ownership(app):
    with app.app_context():
        resident, _ = auth_service.register_user(
            name="Resident",
            email="b1-exact@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )

        cat = IncidentCategory(name="water_leak", description="Water leak", is_active=True)
        auth = Authority(name="Water Dept", is_active=True, notifications_enabled=True)
        db.session.add_all([cat, auth])

        loc_root = Location(
            location_type="municipality", municipality="M1", parent_location_id=None
        )
        db.session.add(loc_root)
        db.session.flush()
        loc_child = Location(location_type="ward", ward="W1", parent_location_id=loc_root.id)
        db.session.add(loc_child)
        db.session.commit()

        rule = RoutingRule(
            category_id=cat.id,
            authority_id=auth.id,
            location_id=loc_child.id,
            priority=1,
            is_active=True,
        )
        db.session.add(rule)
        db.session.commit()

        files = [FileStorage(stream=io.BytesIO(MINIMAL_PNG_BYTES), filename="e.png")]
        incident, errors = incident_service.create_incident(
            _payload(category_id=cat.id, category=cat.name, location_id=loc_child.id),
            resident,
            files=files,
        )
        assert incident is not None
        assert not errors
        assert incident.suggested_authority_id == auth.id
        assert incident.current_authority_id == auth.id
        assert incident.requires_admin_review is False

        assignments = (
            db.session.query(IncidentAssignment)
            .filter(IncidentAssignment.incident_id == incident.id)
            .all()
        )
        assert len(assignments) == 1
        assert assignments[0].authority_id == auth.id
        assert assignments[0].assigned_by_user_id is None

        current_ownership = incident_service.ownership_repo.get_current(incident.id)
        assert current_ownership is not None
        assert current_ownership.authority_id == auth.id

        dispatches = (
            db.session.query(IncidentDispatch)
            .filter(IncidentDispatch.incident_id == incident.id)
            .all()
        )
        assert len(dispatches) == 0

        events = incident_service.event_repo.list_for_incident(incident.id)
        assert any(e.event_type == IncidentEventType.ROUTE_APPLIED.value for e in events)


def test_b1_auto_assign_parent_does_not_commit_assignment(app):
    with app.app_context():
        resident, _ = auth_service.register_user(
            name="Resident",
            email="b1-parent@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )

        cat = IncidentCategory(name="water_leak", description="Water leak", is_active=True)
        parent_auth = Authority(name="Parent Dept", is_active=True, notifications_enabled=True)
        global_auth = Authority(name="Global Dept", is_active=True, notifications_enabled=True)
        db.session.add_all([cat, parent_auth, global_auth])

        loc_root = Location(
            location_type="municipality", municipality="M1", parent_location_id=None
        )
        db.session.add(loc_root)
        db.session.flush()
        loc_parent = Location(
            location_type="district", district="D1", parent_location_id=loc_root.id
        )
        db.session.add(loc_parent)
        db.session.flush()
        loc_child = Location(location_type="ward", ward="W1", parent_location_id=loc_parent.id)
        db.session.add(loc_child)
        db.session.commit()

        r_parent = RoutingRule(
            category_id=cat.id,
            authority_id=parent_auth.id,
            location_id=loc_parent.id,  # ancestor => medium
            priority=1,
            is_active=True,
        )
        r_global = RoutingRule(
            category_id=cat.id,
            authority_id=global_auth.id,
            location_id=None,
            priority=10,
            is_active=True,
        )
        db.session.add_all([r_parent, r_global])
        db.session.commit()

        files = [FileStorage(stream=io.BytesIO(MINIMAL_PNG_BYTES), filename="e.png")]
        incident, errors = incident_service.create_incident(
            _payload(category_id=cat.id, category=cat.name, location_id=loc_child.id),
            resident,
            files=files,
        )
        assert incident is not None
        assert not errors
        assert incident.suggested_authority_id == parent_auth.id
        assert incident.current_authority_id is None
        assert incident.requires_admin_review is True

        assignments = (
            db.session.query(IncidentAssignment)
            .filter(IncidentAssignment.incident_id == incident.id)
            .all()
        )
        assert len(assignments) == 0


def test_b1_auto_assign_global_fallback_does_not_commit_assignment(app):
    with app.app_context():
        resident, _ = auth_service.register_user(
            name="Resident",
            email="b1-global@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )

        cat = IncidentCategory(name="water_leak", description="Water leak", is_active=True)
        global_auth = Authority(name="Global Dept", is_active=True, notifications_enabled=True)
        db.session.add_all([cat, global_auth])

        loc_root = Location(
            location_type="municipality", municipality="M1", parent_location_id=None
        )
        db.session.add(loc_root)
        db.session.flush()
        loc_child = Location(location_type="ward", ward="W1", parent_location_id=loc_root.id)
        db.session.add(loc_child)
        db.session.commit()

        r_global = RoutingRule(
            category_id=cat.id,
            authority_id=global_auth.id,
            location_id=None,  # global fallback => low
            priority=10,
            is_active=True,
        )
        db.session.add(r_global)
        db.session.commit()

        files = [FileStorage(stream=io.BytesIO(MINIMAL_PNG_BYTES), filename="e.png")]
        incident, errors = incident_service.create_incident(
            _payload(category_id=cat.id, category=cat.name, location_id=loc_child.id),
            resident,
            files=files,
        )
        assert incident is not None
        assert not errors
        assert incident.suggested_authority_id == global_auth.id
        assert incident.current_authority_id is None
        assert incident.requires_admin_review is True

        assignments = (
            db.session.query(IncidentAssignment)
            .filter(IncidentAssignment.incident_id == incident.id)
            .all()
        )
        assert len(assignments) == 0
