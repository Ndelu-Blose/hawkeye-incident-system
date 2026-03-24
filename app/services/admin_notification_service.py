from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.extensions import db
from app.models.admin_notification_state import AdminNotificationState
from app.models.notification_log import NotificationLog
from app.models.user import User
from app.utils.datetime_helpers import utc_now


@dataclass(frozen=True)
class AdminNotificationItem:
    id: int
    created_at: datetime
    title: str
    body: str
    incident_id: int | None
    link_url: str | None
    is_unread: bool


class AdminNotificationService:
    def ensure_state(self, user: User) -> AdminNotificationState:
        state = db.session.execute(
            select(AdminNotificationState).where(AdminNotificationState.user_id == user.id)
        ).scalar_one_or_none()
        if state is not None:
            return state

        state = AdminNotificationState(user_id=user.id, last_seen_at=utc_now())
        db.session.add(state)
        db.session.commit()
        return state

    def unread_count(self, user: User) -> int:
        state = self.ensure_state(user)
        return int(
            db.session.execute(
                select(func.count(NotificationLog.id)).where(
                    NotificationLog.user_id == user.id,
                    NotificationLog.created_at > state.last_seen_at,
                )
            ).scalar()
            or 0
        )

    def list_items(self, user: User, *, limit: int = 20) -> list[AdminNotificationItem]:
        state = self.ensure_state(user)
        rows = list(
            db.session.execute(
                select(NotificationLog)
                .where(NotificationLog.user_id == user.id)
                .order_by(NotificationLog.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        items: list[AdminNotificationItem] = []
        for row in rows:
            if not row.created_at:
                continue
            title, body, link_url = self._to_text(row)
            created_at = (
                row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=UTC)
            )
            items.append(
                AdminNotificationItem(
                    id=row.id,
                    created_at=created_at,
                    title=title,
                    body=body,
                    incident_id=row.incident_id,
                    link_url=link_url,
                    is_unread=bool(row.created_at > state.last_seen_at),
                )
            )
        return items

    def mark_read(self, user: User, notification_id: int) -> bool:
        row = db.session.get(NotificationLog, notification_id)
        if row is None or row.user_id != user.id:
            return False
        state = self.ensure_state(user)
        target = row.created_at or utc_now()
        if state.last_seen_at < target:
            state.last_seen_at = target
            db.session.commit()
        return True

    def mark_all_read(self, user: User) -> None:
        state = self.ensure_state(user)
        state.last_seen_at = utc_now()
        db.session.commit()

    @staticmethod
    def _to_text(row: NotificationLog) -> tuple[str, str, str | None]:
        ntype = (row.type or "").strip().lower()
        incident_ref = f"#{row.incident_id}" if row.incident_id else ""
        link = f"/admin/incidents/{row.incident_id}" if row.incident_id else None
        if ntype == "proof_submitted":
            return (
                f"New proof submitted {incident_ref}".strip(),
                "Resident added additional evidence and incident is ready for admin review.",
                link,
            )
        if ntype == "incident_created":
            return (f"New incident {incident_ref}".strip(), "A new incident was created.", link)
        if ntype == "status_changed":
            return (
                f"Incident status changed {incident_ref}".strip(),
                "An incident status was updated.",
                link,
            )
        return ("Notification", f"Notification type: {row.type}", link)


admin_notification_service = AdminNotificationService()
