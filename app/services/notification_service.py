from __future__ import annotations

from collections.abc import Iterable

from flask import current_app
from sqlalchemy import select

from app.constants import Roles
from app.extensions import db
from app.models.incident import Incident
from app.models.notification_log import NotificationLog
from app.models.user import User
from app.repositories.notification_repo import NotificationRepository
from app.services.resend_email import send_outbound_email, text_to_html_email
from app.utils.datetime_helpers import utc_now


class NotificationService:
    """Create NotificationLog entries for in-app and email notifications."""

    def __init__(
        self,
        notification_repo: NotificationRepository | None = None,
    ) -> None:
        self.notification_repo = notification_repo or NotificationRepository()

    def enqueue_incident_created(
        self,
        incident: Incident,
        authority_users: Iterable[User],
        *,
        event_id: int | None = None,
    ) -> None:
        for user in authority_users:
            notification = NotificationLog(
                incident_id=incident.id,
                event_id=event_id,
                user_id=user.id,
                recipient_email=user.email,
                type="incident_created",
                status="queued",
            )
            self.notification_repo.add(notification)

    def enqueue_incident_submitted(
        self,
        incident: Incident,
        resident: User,
    ) -> None:
        """Email the reporter confirming we received their incident."""
        notification = NotificationLog(
            incident_id=incident.id,
            user_id=resident.id,
            recipient_email=resident.email,
            type="incident_submitted",
            status="queued",
        )
        self.notification_repo.add(notification)

    def enqueue_status_changed(
        self,
        incident: Incident,
        resident: User,
        *,
        event_id: int | None = None,
    ) -> None:
        notification = NotificationLog(
            incident_id=incident.id,
            event_id=event_id,
            user_id=resident.id,
            recipient_email=resident.email,
            type="status_changed",
            status="queued",
        )
        self.notification_repo.add(notification)

    def enqueue_admins_proof_submitted(
        self,
        incident: Incident,
        *,
        event_id: int | None = None,
    ) -> None:
        admins = list(
            db.session.execute(
                select(User).where(
                    User.role == Roles.ADMIN.value,
                    User.is_active.is_(True),
                )
            )
            .scalars()
            .all()
        )
        for admin in admins:
            self.notification_repo.add(
                NotificationLog(
                    incident_id=incident.id,
                    event_id=event_id,
                    user_id=admin.id,
                    recipient_email=admin.email,
                    type="proof_submitted",
                    status="queued",
                )
            )

    def commit(self) -> None:
        db.session.commit()

    def process_queued(self, *, limit: int = 50) -> dict[str, int]:
        """Send queued notifications and update delivery status."""
        queued = list(self.notification_repo.list_queued(limit=limit))
        sent = 0
        failed = 0
        for notification in queued:
            try:
                subject, body = self._compose_message(notification)
                recipient = (notification.recipient_email or "").strip()
                if not recipient:
                    raise ValueError("Recipient email is missing.")
                html = text_to_html_email(body)
                ok, err, provider = send_outbound_email(
                    current_app,
                    to_email=recipient,
                    subject=subject,
                    text_body=body,
                    html_body=html,
                )
                if not ok:
                    raise RuntimeError(err or "send_failed")
                notification.status = "sent"
                notification.sent_at = utc_now()
                notification.provider_message_id = provider
                notification.last_error = None
                sent += 1
            except Exception as exc:
                notification.status = "failed"
                notification.last_error = str(exc)
                failed += 1
        db.session.commit()
        return {"processed": len(queued), "sent": sent, "failed": failed}

    @staticmethod
    def _compose_message(notification: NotificationLog) -> tuple[str, str]:
        incident_id = notification.incident_id
        base_url = (current_app.config.get("APP_BASE_URL") or "").rstrip("/")
        incident = db.session.get(Incident, incident_id) if incident_id is not None else None
        ref = (
            (incident.reference_code or f"HK-{incident.id}")
            if incident is not None
            else (f"#{incident_id}" if incident_id else "—")
        )
        resident_incident_url = (
            f"{base_url}/resident/incidents/{incident_id}" if incident_id else base_url or "/"
        )
        admin_incident_url = (
            f"{base_url}/admin/incidents/{incident_id}" if incident_id else base_url or "/"
        )
        status_label = (
            (incident.status or "").replace("_", " ").strip().title()
            if incident is not None
            else "Updated"
        )

        if notification.type == "incident_submitted":
            title = incident.title if incident is not None else "Your report"
            cat = incident.category if incident is not None else "—"
            return (
                f"We received your report ({ref})",
                (
                    "Thank you for using Alertweb Solutions.\n\n"
                    f"Reference: {ref}\n"
                    f"Title: {title}\n"
                    f"Category: {cat}\n"
                    f"Current status: {status_label}\n\n"
                    "We will email you again when there is a meaningful status update.\n"
                    f"View your incident: {resident_incident_url}\n"
                ),
            )

        if notification.type == "incident_created":
            return (
                f"New incident assigned ({ref})",
                (
                    "A new incident has been escalated and is awaiting authority action.\n\n"
                    f"Incident: {ref}\n"
                    f"Status: {status_label}\n"
                    f"View details: {resident_incident_url}\n"
                ),
            )
        if notification.type == "status_changed":
            return (
                f"Incident update ({ref}): {status_label}",
                (
                    "There is an update on your incident.\n\n"
                    f"Reference: {ref}\n"
                    f"Current status: {status_label}\n"
                    f"View details: {resident_incident_url}\n"
                ),
            )
        if notification.type == "proof_submitted":
            return (
                f"New proof submitted ({ref})",
                (
                    "A resident has submitted additional proof and the incident is ready for review.\n\n"
                    f"Incident: {ref}\n"
                    f"Review incident: {admin_incident_url}\n"
                ),
            )
        return (
            f"Alertweb Solutions notification ({ref})",
            f"Notification type: {notification.type}\nView details: {resident_incident_url}\n",
        )


notification_service = NotificationService()
