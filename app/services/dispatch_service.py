from __future__ import annotations

from dataclasses import dataclass

from flask import current_app
from flask_mail import Message

from app.extensions import db, mail
from app.models import Authority, DepartmentContact, Incident, IncidentDispatch
from app.utils.datetime_helpers import utc_now


@dataclass
class DispatchResult:
    ok: bool
    recipient_email: str | None
    error: str | None = None


class DispatchService:
    """Department dispatch helper (contact resolution + email send + dispatch log updates)."""

    @staticmethod
    def _resolve_email_contact(authority: Authority) -> DepartmentContact | None:
        if authority is None:
            return None
        query = db.session.query(DepartmentContact).filter(
            DepartmentContact.authority_id == authority.id,
            DepartmentContact.is_active.is_(True),
            DepartmentContact.channel == "email",
        )
        priority_order = [
            ("verified", True, False),
            ("verified", False, True),
            ("unverified", True, False),
        ]
        for verification_status, is_primary, is_secondary in priority_order:
            contact = (
                query.filter(
                    DepartmentContact.verification_status == verification_status,
                    DepartmentContact.is_primary.is_(is_primary),
                    DepartmentContact.is_secondary.is_(is_secondary),
                )
                .order_by(DepartmentContact.id.asc())
                .first()
            )
            if contact is not None:
                return contact
        return query.order_by(DepartmentContact.id.asc()).first()

    @staticmethod
    def resolve_primary_email(authority: Authority) -> str | None:
        contact = DispatchService._resolve_email_contact(authority)
        return (contact.value or "").strip() if contact is not None else None

    @staticmethod
    def compose_work_order(incident: Incident, authority: Authority) -> tuple[str, str]:
        reference = incident.reference_code or f"INC-{incident.id}"
        subject = f"[Alertweb Dispatch] {reference} | {incident.category} | {incident.severity}"
        maps_link = ""
        if incident.latitude is not None and incident.longitude is not None:
            maps_link = f"https://maps.google.com/?q={float(incident.latitude):.6f},{float(incident.longitude):.6f}"
        body = "\n".join(
            [
                "New Incident Dispatch",
                "",
                f"Reference: {reference}",
                f"Category: {incident.category}",
                f"Priority: {incident.severity}",
                f"Reported: {(incident.reported_at or incident.created_at)}",
                f"Department: {authority.name}",
                "",
                "Location",
                f"{incident.location}",
                (
                    f"GPS: {float(incident.latitude):.6f}, {float(incident.longitude):.6f}"
                    if incident.latitude is not None and incident.longitude is not None
                    else "GPS: Not provided"
                ),
                f"Maps Link: {maps_link or 'Not available'}",
                "",
                "Description",
                incident.description or "-",
                "",
                "Action Required",
                "Please acknowledge receipt and begin response handling.",
                "Reply with your official municipal reference number when available.",
            ]
        )
        return subject, body

    def send_assignment_dispatch(self, dispatch: IncidentDispatch) -> DispatchResult:
        incident = dispatch.incident
        authority = dispatch.authority
        if incident is None or authority is None:
            dispatch.status = "failed"
            dispatch.failure_reason = "Incident or department missing for dispatch."
            dispatch.last_status_update_at = utc_now()
            return DispatchResult(ok=False, recipient_email=None, error=dispatch.failure_reason)
        if not authority.notifications_enabled:
            dispatch.status = "failed"
            dispatch.failure_reason = "Department notifications are disabled."
            dispatch.last_status_update_at = utc_now()
            return DispatchResult(ok=False, recipient_email=None, error=dispatch.failure_reason)
        recipient = self.resolve_primary_email(authority)
        if not recipient:
            dispatch.status = "failed"
            dispatch.failure_reason = (
                "No dispatchable email contact configured "
                "(requires active contact; verified primary/secondary preferred)."
            )
            dispatch.last_status_update_at = utc_now()
            return DispatchResult(ok=False, recipient_email=None, error=dispatch.failure_reason)

        subject, body = self.compose_work_order(incident, authority)
        dispatch.recipient_email = recipient
        dispatch.subject_snapshot = subject
        dispatch.message_snapshot = body
        dispatch.status = "pending"
        dispatch.last_status_update_at = utc_now()

        try:
            msg = Message(subject=subject, recipients=[recipient], body=body)
            mail.send(msg)
            now = utc_now()
            dispatch.status = "sent"
            dispatch.delivery_status = "sent"
            dispatch.delivery_provider = "flask-mail"
            dispatch.delivery_reference = "flask-mail"
            dispatch.sent_at = dispatch.sent_at or now
            dispatch.last_status_update_at = now
            return DispatchResult(ok=True, recipient_email=recipient)
        except Exception as exc:
            dispatch.status = "failed"
            dispatch.delivery_status = "failed"
            dispatch.failure_reason = str(exc)
            dispatch.last_status_update_at = utc_now()
            return DispatchResult(ok=False, recipient_email=recipient, error=str(exc))

    def retry_dispatch(self, dispatch: IncidentDispatch) -> DispatchResult:
        """Retry a previously failed/pending dispatch."""
        dispatch.failure_reason = None
        dispatch.last_status_update_at = utc_now()
        return self.send_assignment_dispatch(dispatch)

    def list_escalation_candidates(
        self,
        *,
        limit: int = 100,
        statuses: list[str] | None = None,
        authority_id: int | None = None,
        min_reminders: int | None = None,
    ) -> list[IncidentDispatch]:
        """Return stale unacknowledged dispatches eligible for reminder/escalation."""
        stale_minutes = int(current_app.config.get("DISPATCH_REMINDER_STALE_MINUTES", 60))
        cooldown_minutes = int(
            current_app.config.get("DISPATCH_REMINDER_RETRY_COOLDOWN_MINUTES", 30)
        )
        max_reminders = int(current_app.config.get("DISPATCH_MAX_REMINDERS", 3))
        now = utc_now()
        stale_cutoff = now.timestamp() - (stale_minutes * 60)
        cooldown_cutoff = now.timestamp() - (cooldown_minutes * 60)

        base_statuses = tuple(statuses or ["pending", "sent", "failed"])
        query = db.session.query(IncidentDispatch).filter(
            IncidentDispatch.ack_status == "pending",
            IncidentDispatch.status.in_(base_statuses),
            IncidentDispatch.reminder_count < max_reminders,
        )
        if authority_id is not None:
            query = query.filter(IncidentDispatch.authority_id == authority_id)
        if min_reminders is not None:
            query = query.filter(IncidentDispatch.reminder_count >= max(0, min_reminders))
        candidates = (
            query.order_by(IncidentDispatch.last_status_update_at.asc().nullsfirst())
            .limit(limit)
            .all()
        )

        eligible: list[IncidentDispatch] = []
        for dispatch in candidates:
            sent_at = dispatch.sent_at or dispatch.created_at
            last_activity = dispatch.last_reminder_at or dispatch.last_status_update_at or sent_at
            if sent_at is None or last_activity is None:
                continue
            if sent_at.timestamp() > stale_cutoff:
                continue
            if dispatch.status == "failed" and last_activity.timestamp() > cooldown_cutoff:
                continue
            if dispatch.next_reminder_at is not None and dispatch.next_reminder_at > now:
                continue
            eligible.append(dispatch)
        return eligible

    def process_auto_escalations(self, *, limit: int = 100) -> dict[str, int]:
        """Send reminder emails for stale/unacknowledged dispatches."""
        if not current_app.config.get("DISPATCH_AUTO_ESCALATION_ENABLED", True):
            return {"processed": 0, "reminders_sent": 0, "failed": 0}
        now = utc_now()
        candidates = self.list_escalation_candidates(limit=limit)

        processed = 0
        reminders_sent = 0
        failed = 0
        for dispatch in candidates:
            processed += 1
            result = self.send_assignment_dispatch(dispatch)
            if result.ok:
                dispatch.reminder_count = int(dispatch.reminder_count or 0) + 1
                dispatch.last_reminder_at = now
                dispatch.next_reminder_at = None
                reminders_sent += 1
            else:
                dispatch.reminder_count = int(dispatch.reminder_count or 0) + 1
                dispatch.last_reminder_at = now
                dispatch.next_reminder_at = None
                failed += 1

        db.session.commit()
        return {"processed": processed, "reminders_sent": reminders_sent, "failed": failed}


dispatch_service = DispatchService()
