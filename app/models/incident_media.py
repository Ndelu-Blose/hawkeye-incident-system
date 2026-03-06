from __future__ import annotations

from app.extensions import db
from app.utils.datetime_helpers import utc_now


class IncidentMedia(db.Model):
    __tablename__ = "incident_media"

    id = db.Column(db.Integer, primary_key=True)

    incident_id = db.Column(
        db.Integer,
        db.ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    file_path = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(255), nullable=True)
    content_type = db.Column(db.String(100), nullable=True)
    filesize_bytes = db.Column(db.Integer, nullable=True)

    uploaded_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    incident = db.relationship(
        "Incident",
        back_populates="media",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<IncidentMedia id={self.id} incident_id={self.incident_id}>"
