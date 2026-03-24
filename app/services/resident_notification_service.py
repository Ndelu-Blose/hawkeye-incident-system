from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.constants import IncidentEventType
from app.extensions import db
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent
from app.models.notification_log import NotificationLog
from app.models.resident_notification_state import ResidentNotificationState
from app.models.user import User
from app.utils.datetime_helpers import utc_now


@dataclass(frozen=True)
class NotificationItem:
    source: str  # incident_event | notification_log
    source_id: int
    created_at: datetime
    title: str
    body: str
    incident_id: int | None
    link_url: str | None
    is_unread: bool


class ResidentNotificationService:
    def ensure_state(self, user: User) -> ResidentNotificationState:
        """Ensure state exists; default to seen-now to avoid infinite unread on first visit."""
        state = db.session.execute(
            select(ResidentNotificationState).where(ResidentNotificationState.user_id == user.id)
        ).scalar_one_or_none()
        if state is not None:
            return state

        state = ResidentNotificationState(user_id=user.id, last_seen_at=utc_now())
        db.session.add(state)
        db.session.commit()
        return state

    def mark_all_read(self, user: User) -> ResidentNotificationState:
        state = self.ensure_state(user)
        state.last_seen_at = utc_now()
        db.session.commit()
        return state

    def unread_count(self, user: User) -> int:
        state = self.ensure_state(user)
        cutoff = state.last_seen_at

        incident_ids_subq = select(Incident.id).where(Incident.reported_by_id == user.id)

        ev_count = int(
            db.session.execute(
                select(func.count(IncidentEvent.id)).where(
                    IncidentEvent.incident_id.in_(incident_ids_subq),
                    IncidentEvent.created_at > cutoff,
                )
            ).scalar()
            or 0
        )
        notif_count = int(
            db.session.execute(
                select(func.count(NotificationLog.id)).where(
                    NotificationLog.user_id == user.id,
                    NotificationLog.created_at > cutoff,
                )
            ).scalar()
            or 0
        )
        return ev_count + notif_count

    def list_items(self, user: User, *, limit: int = 50) -> list[NotificationItem]:
        state = self.ensure_state(user)
        cutoff = state.last_seen_at

        incident_ids_subq = select(Incident.id).where(Incident.reported_by_id == user.id)

        ev_rows = list(
            db.session.execute(
                select(IncidentEvent)
                .where(IncidentEvent.incident_id.in_(incident_ids_subq))
                .order_by(IncidentEvent.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        notif_rows = list(
            db.session.execute(
                select(NotificationLog)
                .where(NotificationLog.user_id == user.id)
                .order_by(NotificationLog.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

        items: list[NotificationItem] = []
        for ev in ev_rows:
            if not ev.created_at:
                continue
            title, body = self._incident_event_text(ev)
            items.append(
                NotificationItem(
                    source="incident_event",
                    source_id=ev.id,
                    created_at=self._ensure_tz(ev.created_at),
                    title=title,
                    body=body,
                    incident_id=ev.incident_id,
                    link_url=f"/resident/incidents/{ev.incident_id}",
                    is_unread=bool(ev.created_at and ev.created_at > cutoff),
                )
            )
        for n in notif_rows:
            if not n.created_at:
                continue
            title, body, link = self._notification_log_text(n)
            items.append(
                NotificationItem(
                    source="notification_log",
                    source_id=n.id,
                    created_at=self._ensure_tz(n.created_at),
                    title=title,
                    body=body,
                    incident_id=n.incident_id,
                    link_url=link,
                    is_unread=bool(n.created_at and n.created_at > cutoff),
                )
            )

        items.sort(key=lambda i: i.created_at, reverse=True)
        return items[:limit]

    @staticmethod
    def _ensure_tz(dt: datetime) -> datetime:
        # Existing DB rows may be naive; treat as UTC for ordering/display.
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)

    @staticmethod
    def _incident_event_text(ev: IncidentEvent) -> tuple[str, str]:
        note = (ev.note or "").strip()
        if ev.event_type == IncidentEventType.INCIDENT_CREATED.value:
            return "Incident reported", note or "Your incident was submitted."
        if ev.event_type == IncidentEventType.INCIDENT_ACKNOWLEDGED.value:
            auth = ev.authority.name if ev.authority else "Department"
            return "Department acknowledged", note or f"Acknowledged by {auth}."
        if ev.event_type in (
            IncidentEventType.INCIDENT_ASSIGNED.value,
            IncidentEventType.DISPATCH_CREATED.value,
            IncidentEventType.DISPATCH_DELIVERED.value,
        ):
            auth = ev.authority.name if ev.authority else "Department"
            return f"Dispatched to {auth}", note or "Your incident was dispatched for action."
        if ev.event_type == IncidentEventType.EVIDENCE_UPLOADED.value:
            return "Evidence uploaded", note or "Evidence was added to the incident."

        f = (ev.from_status or "").strip()
        t = (ev.to_status or "").strip()
        if f and t and f != t:
            title = f"Status updated: {f.replace('_', ' ').title()} → {t.replace('_', ' ').title()}"
        elif t:
            title = f"Status updated: {t.replace('_', ' ').title()}"
        else:
            title = "Incident updated"
        return title, note or "There was an update to your incident."

    @staticmethod
    def _notification_log_text(n: NotificationLog) -> tuple[str, str, str | None]:
        kind = (n.type or "").strip().lower()
        if kind == "status_changed":
            return (
                "Status change notification",
                "We sent you an update about an incident status change.",
                f"/resident/incidents/{n.incident_id}" if n.incident_id else None,
            )
        if kind == "incident_created":
            return (
                "New incident notification",
                "An incident notification was generated.",
                f"/resident/incidents/{n.incident_id}" if n.incident_id else None,
            )
        return (
            "Notification",
            f"Notification type: {n.type}",
            f"/resident/incidents/{n.incident_id}" if n.incident_id else None,
        )


resident_notification_service = ResidentNotificationService()
