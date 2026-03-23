"""Ownership history: who owned the incident when. Exactly one current row per incident."""

from __future__ import annotations

from app.extensions import db
from app.utils.datetime_helpers import utc_now


class IncidentOwnershipHistory(db.Model):
    """Tracks ownership of incidents. One row per assignment period."""

    __tablename__ = "incident_ownership_history"

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

    assigned_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    ended_at = db.Column(db.DateTime, nullable=True)
    is_current = db.Column(db.Boolean, nullable=False, default=True)

    dispatch_id = db.Column(
        db.Integer,
        db.ForeignKey("incident_dispatches.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason = db.Column(db.Text, nullable=True)

    incident = db.relationship("Incident", back_populates="ownership_history")
    authority = db.relationship("Authority", foreign_keys=[authority_id])
    assigned_by = db.relationship("User", foreign_keys=[assigned_by_user_id])
    dispatch = db.relationship("IncidentDispatch", foreign_keys=[dispatch_id])

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<IncidentOwnershipHistory id={self.id} incident_id={self.incident_id} "
            f"authority_id={self.authority_id} is_current={self.is_current}>"
        )
