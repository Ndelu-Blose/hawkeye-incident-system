"""Repository for audit_logs."""

from __future__ import annotations

from sqlalchemy import select

from app.extensions import db
from app.models.audit_log import AuditLog


class AuditRepository:
    """Repository for immutable audit log records."""

    def add(self, log: AuditLog) -> None:
        """Persist an audit log (caller must commit)."""
        db.session.add(log)

    def create(
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
    ) -> AuditLog:
        """Create and add an audit log. Caller must commit."""
        log = AuditLog(
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
        self.add(log)
        return log

    def list_for_entity(
        self,
        entity_type: str,
        entity_id: int,
        limit: int = 100,
    ) -> list[AuditLog]:
        """Return audit logs for an entity, newest first."""
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == entity_id,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(db.session.execute(stmt).scalars().all())
