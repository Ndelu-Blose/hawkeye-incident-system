from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select

from app.extensions import db
from app.models.notification_log import NotificationLog


class NotificationRepository:
    """Data access helper for NotificationLog entries (outbox pattern)."""

    def add(self, notification: NotificationLog) -> NotificationLog:
        db.session.add(notification)
        return notification

    def get_by_id(self, notification_id: int) -> NotificationLog | None:
        return db.session.get(NotificationLog, notification_id)

    def list_queued(self, limit: int = 50) -> Iterable[NotificationLog]:
        stmt = (
            select(NotificationLog)
            .where(NotificationLog.status == "queued")
            .order_by(NotificationLog.created_at.asc())
            .limit(limit)
        )
        return db.session.execute(stmt).scalars().all()

    def list_failed(self, limit: int = 100) -> Iterable[NotificationLog]:
        stmt = (
            select(NotificationLog)
            .where(NotificationLog.status == "failed")
            .order_by(NotificationLog.created_at.asc())
            .limit(limit)
        )
        return db.session.execute(stmt).scalars().all()

    def requeue_failed(self, limit: int = 100) -> int:
        failed = list(self.list_failed(limit=limit))
        for notification in failed:
            notification.status = "queued"
            notification.last_error = None
            notification.sent_at = None
            notification.provider_message_id = None
        return len(failed)
