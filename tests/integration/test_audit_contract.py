"""Contract tests: sensitive actions write exactly one audit_logs row."""

from app.constants import IncidentStatus, Roles
from app.extensions import db
from app.models.incident import Incident
from app.repositories.audit_repo import AuditRepository
from app.services.auth_service import auth_service
from app.services.incident_service import incident_service


def _audit_count(incident_id: int) -> int:
    return len(AuditRepository().list_for_entity("incident", incident_id))


def _make_incident_with_admin(app, status: IncidentStatus):
    """Create resident, admin, incident. Caller must be in app_context."""
    resident, _ = auth_service.register_user(
        name="Resident",
        email="audit-res@example.com",
        password="pass",
        role=Roles.RESIDENT.value,
    )
    admin, _ = auth_service.register_user(
        name="Admin",
        email="audit-admin@example.com",
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
    from app.models.user import User

    return incident, db.session.get(User, admin.id)


def test_reject_writes_audit(app):
    """Reject with valid reason writes exactly one audit row."""
    with app.app_context():
        incident, admin_user = _make_incident_with_admin(app, IncidentStatus.REPORTED)
        before = _audit_count(incident.id)

        ok, errors = incident_service.update_status(
            incident.id,
            IncidentStatus.REJECTED,
            note="Duplicate report",
            authority_user=admin_user,
            allow_admin_override=True,
        )
        assert ok, errors

        after = _audit_count(incident.id)
        assert after == before + 1
        logs = AuditRepository().list_for_entity("incident", incident.id)
        reject_logs = [log for log in logs if log.action == "incident_rejected"]
        assert len(reject_logs) == 1
        assert reject_logs[0].reason == "Duplicate report"
        assert reject_logs[0].before_json.get("status") == IncidentStatus.REPORTED.value
        assert reject_logs[0].after_json.get("status") == IncidentStatus.REJECTED.value


def test_reject_without_reason_fails(app):
    """Reject without reason fails."""
    with app.app_context():
        incident, admin_user = _make_incident_with_admin(app, IncidentStatus.REPORTED)
        before = _audit_count(incident.id)

        ok, errors = incident_service.update_status(
            incident.id,
            IncidentStatus.REJECTED,
            note="",
            authority_user=admin_user,
            allow_admin_override=True,
        )
        assert not ok
        assert "reason" in str(errors).lower() or "required" in str(errors).lower()

        after = _audit_count(incident.id)
        assert after == before


def test_manual_close_writes_audit(app):
    """Manual close (resolved -> closed) with reason writes exactly one audit row."""
    with app.app_context():
        incident, admin_user = _make_incident_with_admin(app, IncidentStatus.RESOLVED)
        before = _audit_count(incident.id)

        ok, errors = incident_service.update_status(
            incident.id,
            IncidentStatus.CLOSED,
            note="Case closed per policy",
            authority_user=admin_user,
            allow_admin_override=True,
        )
        assert ok, errors

        after = _audit_count(incident.id)
        assert after == before + 1
        logs = AuditRepository().list_for_entity("incident", incident.id)
        close_logs = [log for log in logs if log.action == "incident_manual_close"]
        assert len(close_logs) == 1
        assert "policy" in close_logs[0].reason.lower() or close_logs[0].reason
        assert close_logs[0].before_json.get("status") == IncidentStatus.RESOLVED.value
        assert close_logs[0].after_json.get("status") == IncidentStatus.CLOSED.value


def test_manual_close_without_reason_fails(app):
    """Manual close without reason fails."""
    with app.app_context():
        incident, admin_user = _make_incident_with_admin(app, IncidentStatus.RESOLVED)
        before = _audit_count(incident.id)

        ok, errors = incident_service.update_status(
            incident.id,
            IncidentStatus.CLOSED,
            note="",
            authority_user=admin_user,
            allow_admin_override=True,
        )
        assert not ok
        assert "reason" in str(errors).lower() or "required" in str(errors).lower()

        after = _audit_count(incident.id)
        assert after == before


def test_override_writes_audit(app):
    """Admin override (invalid transition) with reason writes exactly one audit row."""
    with app.app_context():
        incident, admin_user = _make_incident_with_admin(app, IncidentStatus.REPORTED)
        before = _audit_count(incident.id)

        ok, errors = incident_service.update_status(
            incident.id,
            IncidentStatus.CLOSED,
            note="Emergency override - duplicate",
            authority_user=admin_user,
            allow_admin_override=True,
        )
        assert ok, errors

        after = _audit_count(incident.id)
        assert after == before + 1
        logs = AuditRepository().list_for_entity("incident", incident.id)
        override_logs = [log for log in logs if log.action == "incident_status_override"]
        assert len(override_logs) == 1
        assert override_logs[0].reason
        assert override_logs[0].before_json.get("status") == IncidentStatus.REPORTED.value
        assert override_logs[0].after_json.get("status") == IncidentStatus.CLOSED.value


def test_override_without_reason_fails(app):
    """Override without reason fails."""
    with app.app_context():
        incident, admin_user = _make_incident_with_admin(app, IncidentStatus.REPORTED)
        before = _audit_count(incident.id)

        ok, errors = incident_service.update_status(
            incident.id,
            IncidentStatus.CLOSED,
            note="",
            authority_user=admin_user,
            allow_admin_override=True,
        )
        assert not ok
        assert "reason" in str(errors).lower() or "required" in str(errors).lower()

        after = _audit_count(incident.id)
        assert after == before
