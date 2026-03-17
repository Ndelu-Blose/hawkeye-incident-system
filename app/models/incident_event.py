"""Immutable incident event ledger: one row per domain event."""

from __future__ import annotations

from app.extensions import db
from app.utils.datetime_helpers import utc_now


class IncidentEvent(db.Model):
    """Canonical event ledger for incident lifecycle. Immutable after insert."""

    __tablename__ = "incident_events"

    id = db.Column(db.Integer, primary_key=True)

    incident_id = db.Column(
        db.Integer,
        db.ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event_type = db.Column(db.String(64), nullable=False, index=True)
    from_status = db.Column(db.String(32), nullable=True)
    to_status = db.Column(db.String(32), nullable=True)

    actor_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_role = db.Column(db.String(32), nullable=True)  # resident | admin | system | department

    authority_id = db.Column(
        db.Integer,
        db.ForeignKey("authorities.id", ondelete="SET NULL"),
        nullable=True,
    )
    dispatch_id = db.Column(
        db.Integer,
        db.ForeignKey("incident_dispatches.id", ondelete="SET NULL"),
        nullable=True,
    )

    reason = db.Column(db.Text, nullable=True)
    note = db.Column(db.Text, nullable=True)
    metadata_json = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    incident = db.relationship("Incident", back_populates="incident_events")
    actor = db.relationship("User", foreign_keys=[actor_user_id])
    authority = db.relationship("Authority", foreign_keys=[authority_id])
    dispatch = db.relationship("IncidentDispatch", foreign_keys=[dispatch_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<IncidentEvent id={self.id} incident_id={self.incident_id} event_type={self.event_type}>"
