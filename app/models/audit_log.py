"""Unified audit log: cross-entity, immutable governance log."""

from __future__ import annotations

from app.extensions import db
from app.utils.datetime_helpers import utc_now


class AuditLog(db.Model):
    """Cross-entity audit log for sensitive actions. Immutable after insert."""

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)

    entity_type = db.Column(db.String(32), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=False, index=True)

    action = db.Column(db.String(64), nullable=False)

    actor_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_role = db.Column(db.String(32), nullable=True)

    reason = db.Column(db.Text, nullable=True)
    before_json = db.Column(db.JSON, nullable=True)
    after_json = db.Column(db.JSON, nullable=True)
    metadata_json = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    actor = db.relationship("User", foreign_keys=[actor_user_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog id={self.id} entity={self.entity_type}:{self.entity_id} action={self.action}>"
