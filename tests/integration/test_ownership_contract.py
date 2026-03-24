"""Contract tests: ownership changes are correct."""

from sqlalchemy import select

from app.constants import IncidentStatus, Roles
from app.extensions import db
from app.models import Authority
from app.models.incident import Incident
from app.models.incident_ownership_history import IncidentOwnershipHistory
from app.services.auth_service import auth_service
from app.services.incident_service import incident_service


def _current_ownership(incident_id: int) -> IncidentOwnershipHistory | None:
    return incident_service.ownership_repo.get_current(incident_id)


def _ownership_count(incident_id: int) -> int:
    stmt = select(IncidentOwnershipHistory).where(
        IncidentOwnershipHistory.incident_id == incident_id
    )
    return len(list(db.session.execute(stmt).scalars().all()))


def _current_count(incident_id: int) -> int:
    stmt = select(IncidentOwnershipHistory).where(
        IncidentOwnershipHistory.incident_id == incident_id,
        IncidentOwnershipHistory.is_current.is_(True),
    )
    return len(list(db.session.execute(stmt).scalars().all()))


def test_assignment_creates_ownership(app):
    """screened -> assigned creates exactly one current ownership row."""
    with app.app_context():
        resident, _ = auth_service.register_user(
            name="Resident",
            email="own-res@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        admin, _ = auth_service.register_user(
            name="Admin",
            email="own-admin@example.com",
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
            status=IncidentStatus.SCREENED.value,
            reference_code="HK-2026-03-000001",
        )
        db.session.add(incident)
        db.session.commit()

        assert _current_ownership(incident.id) is None

        ok, errors = incident_service.change_status(
            incident,
            IncidentStatus.ASSIGNED,
            actor_user_id=admin.id,
            actor_role="admin",
            authority_id=auth.id,
        )
        assert ok, errors
        db.session.commit()

        current = _current_ownership(incident.id)
        assert current is not None
        assert current.authority_id == auth.id
        assert current.is_current is True
        assert _current_count(incident.id) == 1


def test_reassignment_ends_prior_ownership(app):
    """Reassignment closes prior ownership and starts new one."""
    with app.app_context():
        resident, _ = auth_service.register_user(
            name="Resident",
            email="own-res2@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        admin, _ = auth_service.register_user(
            name="Admin",
            email="own-admin2@example.com",
            password="pass",
            role=Roles.ADMIN.value,
        )
        auth_a = Authority(name="Dept A", is_active=True)
        auth_b = Authority(name="Dept B", is_active=True)
        db.session.add_all([auth_a, auth_b])
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
            status=IncidentStatus.SCREENED.value,
            reference_code="HK-2026-03-000002",
        )
        db.session.add(incident)
        db.session.commit()

        ok, _ = incident_service.change_status(
            incident,
            IncidentStatus.ASSIGNED,
            actor_user_id=admin.id,
            actor_role="admin",
            authority_id=auth_a.id,
        )
        db.session.commit()

        current = _current_ownership(incident.id)
        assert current.authority_id == auth_a.id

        ok, _ = incident_service.change_status(
            incident,
            IncidentStatus.SCREENED,
            actor_user_id=admin.id,
            actor_role="admin",
            reason="Reassigning to different department",
            allow_admin_override=True,
        )
        assert ok
        db.session.commit()

        incident.status = IncidentStatus.SCREENED.value
        ok, _ = incident_service.change_status(
            incident,
            IncidentStatus.ASSIGNED,
            actor_user_id=admin.id,
            actor_role="admin",
            authority_id=auth_b.id,
        )
        db.session.commit()

        current = _current_ownership(incident.id)
        assert current.authority_id == auth_b.id
        assert _current_count(incident.id) == 1

        all_rows = list(
            db.session.execute(
                select(IncidentOwnershipHistory)
                .where(IncidentOwnershipHistory.incident_id == incident.id)
                .order_by(IncidentOwnershipHistory.assigned_at.asc())
            )
            .scalars()
            .all()
        )
        assert len(all_rows) == 2
        assert all_rows[0].is_current is False
        assert all_rows[0].ended_at is not None
        assert all_rows[1].is_current is True


def test_resolved_closes_ownership(app):
    """in_progress -> resolved closes current ownership."""
    with app.app_context():
        resident, _ = auth_service.register_user(
            name="Resident",
            email="own-res3@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        admin, _ = auth_service.register_user(
            name="Admin",
            email="own-admin3@example.com",
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
            status=IncidentStatus.SCREENED.value,
            reference_code="HK-2026-03-000003",
        )
        db.session.add(incident)
        db.session.commit()

        incident_service.change_status(
            incident,
            IncidentStatus.ASSIGNED,
            actor_user_id=admin.id,
            actor_role="admin",
            authority_id=auth.id,
        )
        db.session.commit()

        incident.status = IncidentStatus.IN_PROGRESS.value
        incident_service.change_status(
            incident,
            IncidentStatus.IN_PROGRESS,
            actor_user_id=admin.id,
            actor_role="admin",
        )
        db.session.commit()

        assert _current_ownership(incident.id) is not None

        incident.status = IncidentStatus.IN_PROGRESS.value
        incident_service.change_status(
            incident,
            IncidentStatus.RESOLVED,
            actor_user_id=admin.id,
            actor_role="admin",
        )
        db.session.commit()

        assert _current_ownership(incident.id) is None
        assert _current_count(incident.id) == 0


def test_never_more_than_one_current(app):
    """At most one is_current=True per incident."""
    with app.app_context():
        resident, _ = auth_service.register_user(
            name="Resident",
            email="own-res4@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        admin, _ = auth_service.register_user(
            name="Admin",
            email="own-admin4@example.com",
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
            status=IncidentStatus.SCREENED.value,
            reference_code="HK-2026-03-000004",
        )
        db.session.add(incident)
        db.session.commit()

        incident_service.change_status(
            incident,
            IncidentStatus.ASSIGNED,
            actor_user_id=admin.id,
            actor_role="admin",
            authority_id=auth.id,
        )
        db.session.commit()

        assert _current_count(incident.id) == 1
