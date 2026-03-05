from __future__ import annotations

from collections.abc import Iterable

from app.extensions import db
from app.models.incident import Incident
from app.models.notification_log import NotificationLog
from app.models.user import User
from app.repositories.notification_repo import NotificationRepository


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
    ) -> None:
        for user in authority_users:
            notification = NotificationLog(
                incident_id=incident.id,
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
    ) -> None:
        notification = NotificationLog(
            incident_id=incident.id,
            user_id=resident.id,
            recipient_email=resident.email,
            type="status_changed",
            status="queued",
        )
        self.notification_repo.add(notification)

    def commit(self) -> None:
        db.session.commit()


notification_service = NotificationService()
