from __future__ import annotations

from app.extensions import db
from app.utils.datetime_helpers import utc_now


class IncidentSlaTracking(db.Model):
    __tablename__ = "incident_sla_tracking"

    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(
        db.Integer,
        db.ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status = db.Column(db.String(20), nullable=False, default="open", index=True)
    sla_hours = db.Column(db.Integer, nullable=False, default=72)
    deadline_at = db.Column(db.DateTime, nullable=False, index=True)
    breached_at = db.Column(db.DateTime, nullable=True, index=True)
    warning_sent_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    incident = db.relationship("Incident", back_populates="sla_tracking", uselist=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<IncidentSlaTracking incident_id={self.incident_id} status={self.status}>"
