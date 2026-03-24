"""Audit service for sensitive actions. Enforces reason for policy-mandated actions."""

from __future__ import annotations

from app.repositories.audit_repo import AuditRepository


class AuditService:
    """Service for writing audit logs. Use for reject, manual close, reopen, override, routing CRUD, user changes."""

    def __init__(self, audit_repo: AuditRepository | None = None) -> None:
        self.audit_repo = audit_repo or AuditRepository()

    def log(
        self,
        entity_type: str,
        entity_id: int,
        action: str,
        *,
        actor_user_id: int | None = None,
        actor_role: str | None = None,
        reason: str | None = None,
        before_json: dict | None = None,
        after_json: dict | None = None,
        metadata_json: dict | None = None,
    ) -> None:
        """Write an audit log entry. Caller must commit."""
        self.audit_repo.create(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            reason=reason,
            before_json=before_json,
            after_json=after_json,
            metadata_json=metadata_json,
        )

    def log_incident_status(
        self,
        incident_id: int,
        action: str,
        *,
        actor_user_id: int | None = None,
        actor_role: str | None = None,
        reason: str | None = None,
        before_status: str | None = None,
        after_status: str | None = None,
    ) -> None:
        """Convenience: audit an incident status change."""
        self.log(
            entity_type="incident",
            entity_id=incident_id,
            action=action,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            reason=reason,
            before_json={"status": before_status} if before_status else None,
            after_json={"status": after_status} if after_status else None,
        )

    def log_routing_rule(
        self,
        rule_id: int,
        action: str,
        *,
        actor_user_id: int | None = None,
        actor_role: str = "admin",
        before_json: dict | None = None,
        after_json: dict | None = None,
    ) -> None:
        """Audit a routing rule change."""
        self.log(
            entity_type="routing_rule",
            entity_id=rule_id,
            action=action,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            before_json=before_json,
            after_json=after_json,
        )

    def log_user_change(
        self,
        user_id: int,
        action: str,
        *,
        actor_user_id: int | None = None,
        actor_role: str = "admin",
        reason: str | None = None,
        before_json: dict | None = None,
        after_json: dict | None = None,
    ) -> None:
        """Audit a user role or activation change."""
        self.log(
            entity_type="user",
            entity_id=user_id,
            action=action,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            reason=reason,
            before_json=before_json,
            after_json=after_json,
        )


audit_service = AuditService()
