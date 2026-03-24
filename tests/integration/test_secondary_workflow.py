from __future__ import annotations

import io

from app.constants import IncidentStatus, Roles
from app.extensions import db
from app.models.authority import Authority
from app.models.incident import Incident
from app.models.incident_category import IncidentCategory
from app.models.incident_dispatch import IncidentDispatch
from app.models.notification_log import NotificationLog
from app.models.routing_rule import RoutingRule
from app.services.auth_service import auth_service
from app.services.notification_service import notification_service
from tests.conftest import MINIMAL_PNG_BYTES


def test_confirm_screening_uses_canonical_flow(app, client):
    with app.app_context():
        resident, _ = auth_service.register_user(
            name="Resident A",
            email="resident.a@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        auth_service.register_user(
            name="Admin A",
            email="admin.a@example.com",
            password="pass",
            role=Roles.ADMIN.value,
        )
        authority = Authority(name="Roads Dept", contact_email="roads@example.com", is_active=True)
        db.session.add(authority)
        db.session.flush()

        incident = Incident(
            reported_by_id=resident.id,
            title="Broken road",
            description="Large pothole",
            category="roads",
            suburb_or_ward="Ward 1",
            street_or_landmark="Main Road",
            location="Main Road, Ward 1",
            severity="high",
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-222001",
            suggested_authority_id=authority.id,
            requires_admin_review=True,
        )
        db.session.add(incident)
        db.session.commit()
        incident_id = incident.id

    client.post(
        "/auth/login",
        data={"email": "admin.a@example.com", "password": "pass"},
        follow_redirects=True,
    )
    resp = client.post(f"/admin/incidents/{incident_id}/screening/confirm", follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        incident = db.session.get(Incident, incident_id)
        assert incident is not None
        assert incident.status == IncidentStatus.ASSIGNED.value
        assert incident.verification_status == "approved"
        assert incident.verified_at is not None
        assert incident.escalated_at is not None
        assert incident.current_authority_id is not None
        dispatch = (
            db.session.query(IncidentDispatch)
            .filter(IncidentDispatch.incident_id == incident_id)
            .order_by(IncidentDispatch.id.desc())
            .first()
        )
        assert dispatch is not None
        assert dispatch.ack_status == "pending"


def test_confirm_screening_backfills_suggestion_from_category_text_routing_rule(app, client):
    with app.app_context():
        resident, _ = auth_service.register_user(
            name="Resident Route",
            email="resident.route@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        auth_service.register_user(
            name="Admin Route",
            email="admin.route@example.com",
            password="pass",
            role=Roles.ADMIN.value,
        )
        authority = Authority(
            name="Metro Police", contact_email="metro@example.com", is_active=True
        )
        category = IncidentCategory(
            name="suspicious_activity",
            description="Suspicious activity",
            is_active=True,
        )
        db.session.add_all([authority, category])
        db.session.flush()
        db.session.add(
            RoutingRule(
                category_id=category.id,
                authority_id=authority.id,
                location_id=None,
                is_active=True,
            )
        )
        db.session.flush()

        # Keep suggestion empty and category text humanized to verify fallback+normalization.
        incident = Incident(
            reported_by_id=resident.id,
            title="Suspicious activity on street",
            description="People tampering near parked cars",
            category="Suspicious Activity",
            suburb_or_ward="Ward 1",
            street_or_landmark="Main Road",
            location="Main Road, Ward 1",
            severity="high",
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-229001",
            suggested_authority_id=None,
        )
        db.session.add(incident)
        db.session.commit()
        incident_id = incident.id
        authority_id = authority.id

    client.post(
        "/auth/login",
        data={"email": "admin.route@example.com", "password": "pass"},
        follow_redirects=True,
    )
    resp = client.post(f"/admin/incidents/{incident_id}/screening/confirm", follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        incident = db.session.get(Incident, incident_id)
        assert incident is not None
        assert incident.suggested_authority_id is not None
        assert incident.current_authority_id == authority_id
        assert incident.status == IncidentStatus.ASSIGNED.value


def test_request_more_proof_and_resubmission_loop(app, client):
    with app.app_context():
        resident, _ = auth_service.register_user(
            name="Resident B",
            email="resident.b@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        auth_service.register_user(
            name="Admin B",
            email="admin.b@example.com",
            password="pass",
            role=Roles.ADMIN.value,
        )
        incident = Incident(
            reported_by_id=resident.id,
            title="Illegal dumping",
            description="Waste dumped near park",
            category="waste",
            suburb_or_ward="Ward 2",
            street_or_landmark="Park Street",
            location="Park Street, Ward 2",
            severity="medium",
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-222002",
        )
        db.session.add(incident)
        db.session.commit()
        incident_id = incident.id

    client.post(
        "/auth/login",
        data={"email": "admin.b@example.com", "password": "pass"},
        follow_redirects=True,
    )
    resp = client.post(
        f"/admin/incidents/{incident_id}/proof/request",
        data={"reason": "Please upload clearer photos of the location and damage."},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        incident = db.session.get(Incident, incident_id)
        assert incident is not None
        assert incident.status == IncidentStatus.AWAITING_EVIDENCE.value
        assert incident.verification_status == "needs_more_evidence"
        assert incident.proof_requested_at is not None

    client.get("/auth/logout", follow_redirects=True)
    client.post(
        "/auth/login",
        data={"email": "resident.b@example.com", "password": "pass"},
        follow_redirects=True,
    )
    resp2 = client.post(
        f"/resident/incidents/{incident_id}/media",
        data={"evidence": (io.BytesIO(MINIMAL_PNG_BYTES), "extra-proof.png")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp2.status_code == 200

    with app.app_context():
        incident = db.session.get(Incident, incident_id)
        assert incident is not None
        # Resident re-submission should return the incident to admin review.
        assert incident.status == IncidentStatus.REPORTED.value
        assert incident.evidence_resubmitted_at is not None
        assert incident.verification_status == "pending"
        assert incident.media.count() >= 1
        assert (
            db.session.query(NotificationLog)
            .filter(
                NotificationLog.incident_id == incident_id,
                NotificationLog.type == "proof_submitted",
                NotificationLog.status == "queued",
            )
            .count()
            >= 1
        )
        updates = incident.updates.all()
        assert any("Additional proof submitted by resident" in (u.note or "") for u in updates)


def test_approve_proof_advances_from_awaiting_evidence(app, client):
    """Approving proof must move the incident out of awaiting_evidence (not only set verification)."""
    with app.app_context():
        resident, _ = auth_service.register_user(
            name="Resident D",
            email="resident.d@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        auth_service.register_user(
            name="Admin D",
            email="admin.d@example.com",
            password="pass",
            role=Roles.ADMIN.value,
        )
        incident = Incident(
            reported_by_id=resident.id,
            title="Fence damage",
            description="Broken fence",
            category="roads",
            suburb_or_ward="Ward 4",
            street_or_landmark="Oak Ave",
            location="Oak Ave, Ward 4",
            severity="medium",
            status=IncidentStatus.AWAITING_EVIDENCE.value,
            verification_status="needs_more_evidence",
            reference_code="HK-2026-03-222004",
        )
        db.session.add(incident)
        db.session.commit()
        incident_id = incident.id

    client.post(
        "/auth/login",
        data={"email": "admin.d@example.com", "password": "pass"},
        follow_redirects=True,
    )
    resp = client.post(
        f"/admin/incidents/{incident_id}/proof/review",
        data={"decision": "approved", "note": "Photos clear enough."},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        incident = db.session.get(Incident, incident_id)
        assert incident is not None
        assert incident.status == IncidentStatus.REPORTED.value
        assert incident.verification_status == "approved"
        assert incident.proof_request_reason is None


def test_notification_queue_processing_marks_sent(app, monkeypatch):
    sent = {"count": 0}

    def fake_send(_msg):
        sent["count"] += 1

    monkeypatch.setattr("app.services.notification_service.mail.send", fake_send)

    with app.app_context():
        resident, _ = auth_service.register_user(
            name="Resident C",
            email="resident.c@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        incident = Incident(
            reported_by_id=resident.id,
            title="Street light off",
            description="Pole light not working",
            category="electricity",
            suburb_or_ward="Ward 3",
            street_or_landmark="3rd Street",
            location="3rd Street, Ward 3",
            severity="low",
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-222003",
        )
        db.session.add(incident)
        db.session.flush()
        db.session.add(
            NotificationLog(
                incident_id=incident.id,
                user_id=resident.id,
                recipient_email=resident.email,
                type="status_changed",
                status="queued",
            )
        )
        db.session.commit()

        result = notification_service.process_queued(limit=20)
        assert result["processed"] >= 1
        assert result["sent"] >= 1
        assert sent["count"] >= 1

        row = db.session.query(NotificationLog).order_by(NotificationLog.id.desc()).first()
        assert row is not None
        assert row.status == "sent"
        assert row.sent_at is not None
