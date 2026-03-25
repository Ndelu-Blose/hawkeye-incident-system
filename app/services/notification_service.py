from __future__ import annotations

from collections.abc import Iterable

from flask import current_app
from flask_mail import Message
from sqlalchemy import select

from app.constants import Roles
from app.extensions import db, mail
from app.models.incident import Incident
from app.models.notification_log import NotificationLog
from app.models.user import User
from app.repositories.notification_repo import NotificationRepository
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
                msg = Message(
                    subject=subject,
                    recipients=[recipient],
                    body=body,
                )
                mail.send(msg)
                notification.status = "sent"
                notification.sent_at = utc_now()
                notification.provider_message_id = "flask-mail"
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
        incident_url = (
            f"{base_url}/resident/incidents/{incident_id}" if incident_id else base_url or "/"
        )
        if notification.type == "incident_created":
            return (
                f"New incident assigned (#{incident_id})",
                (
                    "A new incident has been escalated and is awaiting authority action.\n\n"
                    f"Incident: #{incident_id}\n"
                    f"View details: {incident_url}\n"
                ),
            )
        if notification.type == "status_changed":
            return (
                f"Incident status updated (#{incident_id})",
                (
                    "There is a new status update on your incident.\n\n"
                    f"Incident: #{incident_id}\n"
                    f"View details: {incident_url}\n"
                ),
            )
        if notification.type == "proof_submitted":
            return (
                f"New proof submitted (#{incident_id})",
                (
                    "A resident has submitted additional proof and the incident is ready for review.\n\n"
                    f"Incident: #{incident_id}\n"
                    f"Review incident: {incident_url}\n"
                ),
            )
        return (
            f"Hawkeye notification (#{incident_id})",
            f"Notification type: {notification.type}\nView details: {incident_url}\n",
        )


notification_service = NotificationService()
