from datetime import UTC, datetime, timedelta

from app.constants import Roles
from app.extensions import db
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent
from app.models.notification_log import NotificationLog
from app.models.resident_notification_state import ResidentNotificationState
from app.services.auth_service import auth_service


def test_resident_notifications_scoped_and_unread(app, client):
    now = datetime.now(UTC)
    with app.app_context():
        r1, _ = auth_service.register_user(
            name="Resident One",
            email="rnotif1@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        r2, _ = auth_service.register_user(
            name="Resident Two",
            email="rnotif2@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )

        i1 = Incident(
            reported_by_id=r1.id,
            title="R1 incident",
            description="Desc",
            category="pothole",
            suburb_or_ward="North",
            street_or_landmark="Main St",
            location="Main St, North",
            severity="low",
            status="reported",
            reference_code="HK-2026-03-000001",
        )
        i2 = Incident(
            reported_by_id=r2.id,
            title="R2 incident",
            description="Desc",
            category="dumping",
            suburb_or_ward="South",
            street_or_landmark="Other St",
            location="Other St, South",
            severity="low",
            status="reported",
            reference_code="HK-2026-03-000002",
        )
        db.session.add_all([i1, i2])
        db.session.commit()

        # Events: one for each resident, plus an older one for r1 that should be read.
        db.session.add_all(
            [
                IncidentEvent(
                    incident_id=i1.id,
                    event_type="incident_created",
                    note="R1 created",
                    created_at=now - timedelta(days=2),
                ),
                IncidentEvent(
                    incident_id=i1.id,
                    event_type="status_changed",
                    from_status="reported",
                    to_status="in_progress",
                    note="R1 in progress",
                    created_at=now - timedelta(minutes=30),
                ),
                IncidentEvent(
                    incident_id=i2.id,
                    event_type="status_changed",
                    from_status="reported",
                    to_status="in_progress",
                    note="R2 in progress",
                    created_at=now - timedelta(minutes=20),
                ),
            ]
        )
        db.session.add_all(
            [
                NotificationLog(
                    incident_id=i1.id,
                    user_id=r1.id,
                    recipient_email=r1.email,
                    type="status_changed",
                    status="queued",
                    created_at=now - timedelta(minutes=10),
                ),
                NotificationLog(
                    incident_id=i2.id,
                    user_id=r2.id,
                    recipient_email=r2.email,
                    type="status_changed",
                    status="queued",
                    created_at=now - timedelta(minutes=5),
                ),
            ]
        )

        # r1 last saw notifications 1 hour ago -> should count 2 unread (event + notif)
        db.session.add(
            ResidentNotificationState(user_id=r1.id, last_seen_at=now - timedelta(hours=1))
        )
        db.session.commit()

    client.post(
        "/auth/login",
        data={"email": "rnotif1@example.com", "password": "pass"},
        follow_redirects=True,
    )

    resp = client.get("/resident/notifications")
    assert resp.status_code == 200

    # Should include r1 content, and exclude r2 content.
    assert b"R1 in progress" in resp.data
    assert b"R1 created" in resp.data
    assert b"R2 in progress" not in resp.data

    # Opening the notifications page marks items as seen; no unread badge on first paint.
    assert b"All caught up" in resp.data
    assert b'badge bg-danger">New</span>' not in resp.data

    # Mark all as read remains idempotent after a visit.
    resp2 = client.post("/resident/notifications/mark_read", follow_redirects=True)
    assert resp2.status_code == 200
    assert b"marked as read" in resp2.data.lower()
