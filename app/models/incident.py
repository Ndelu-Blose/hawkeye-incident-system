from __future__ import annotations

from datetime import datetime

from app.constants import IncidentStatus
from app.extensions import db


class Incident(db.Model):
    __tablename__ = "incidents"

    id = db.Column(db.Integer, primary_key=True)

    reported_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    severity = db.Column(db.String(50), nullable=False)

    status = db.Column(
        db.String(32),
        nullable=False,
        default=IncidentStatus.PENDING.value,
        index=True,
    )

    # Optional optimistic concurrency field
    version = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    reporter = db.relationship(
        "User",
        back_populates="incidents_reported",
    )

    updates = db.relationship(
        "IncidentUpdate",
        back_populates="incident",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="IncidentUpdate.created_at",
    )

    notifications = db.relationship(
        "NotificationLog",
        back_populates="incident",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Incident id={self.id} status={self.status}>"

