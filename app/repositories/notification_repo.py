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
