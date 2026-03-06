from __future__ import annotations

from app.extensions import db
from app.utils.datetime_helpers import utc_now


class IncidentUpdate(db.Model):
    __tablename__ = "incident_updates"

    id = db.Column(db.Integer, primary_key=True)

    incident_id = db.Column(
        db.Integer,
        db.ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    updated_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    from_status = db.Column(db.String(32), nullable=True)
    to_status = db.Column(db.String(32), nullable=False)
    note = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    incident = db.relationship(
        "Incident",
        back_populates="updates",
    )

    updater = db.relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<IncidentUpdate id={self.id} incident_id={self.incident_id}>"
