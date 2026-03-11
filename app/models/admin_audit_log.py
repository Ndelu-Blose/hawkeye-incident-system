from __future__ import annotations

from app.extensions import db
from app.utils.datetime_helpers import utc_now


class AdminAuditLog(db.Model):
    __tablename__ = "admin_audit_logs"

    id = db.Column(db.Integer, primary_key=True)

    admin_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    action = db.Column(db.String(64), nullable=False)
    target_type = db.Column(db.String(32), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)

    details = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
