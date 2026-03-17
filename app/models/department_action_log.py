"""Department action log: records actions performed by department users on incidents."""

from __future__ import annotations

from app.extensions import db
from app.utils.datetime_helpers import utc_now


class DepartmentActionLog(db.Model):
    """Log of actions performed by department users on incidents."""

    __tablename__ = "department_action_logs"

    id = db.Column(db.Integer, primary_key=True)

    incident_id = db.Column(
        db.Integer,
        db.ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    authority_id = db.Column(
        db.Integer,
        db.ForeignKey("authorities.id", ondelete="CASCADE"),
        nullable=False,
    )
    performed_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    action_type = db.Column(db.String(64), nullable=False)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    incident = db.relationship("Incident", back_populates="department_action_logs")
    authority = db.relationship("Authority", back_populates="department_action_logs")
    performed_by = db.relationship("User", foreign_keys=[performed_by_id])

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<DepartmentActionLog id={self.id} incident_id={self.incident_id} "
            f"action_type={self.action_type!r}>"
        )
