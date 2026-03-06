from __future__ import annotations

from app.constants import IncidentStatus
from app.extensions import db
from app.utils.datetime_helpers import utc_now


class Incident(db.Model):
    __tablename__ = "incidents"

    id = db.Column(db.Integer, primary_key=True)

    reported_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    resident_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("resident_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False)

    category_id = db.Column(
        db.Integer,
        db.ForeignKey("incident_categories.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Structured location fields
    suburb_or_ward = db.Column(db.String(120), nullable=False)
    street_or_landmark = db.Column(db.String(255), nullable=False)
    nearest_place = db.Column(db.String(255), nullable=True)
    # Backwards-compatible combined location string
    location = db.Column(db.String(255), nullable=False)

    location_id = db.Column(
        db.Integer,
        db.ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    latitude = db.Column(db.Numeric(9, 6), nullable=True)
    longitude = db.Column(db.Numeric(9, 6), nullable=True)

    severity = db.Column(db.String(50), nullable=False)

    status = db.Column(
        db.String(32),
        nullable=False,
        default=IncidentStatus.PENDING.value,
        index=True,
    )

    # Optional optimistic concurrency field
    version = db.Column(db.Integer, nullable=False, default=1)

    reference_no = db.Column(db.String(32), nullable=True, index=True)

    current_authority_id = db.Column(
        db.Integer,
        db.ForeignKey("authorities.id", ondelete="SET NULL"),
        nullable=True,
    )

    is_anonymous = db.Column(db.Boolean, nullable=False, default=False)
    duplicate_of_incident_id = db.Column(
        db.Integer,
        db.ForeignKey("incidents.id", ondelete="SET NULL"),
        nullable=True,
    )

    reported_at = db.Column(db.DateTime, nullable=True)
    acknowledged_at = db.Column(db.DateTime, nullable=True)
    assigned_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    reporter = db.relationship(
        "User",
        back_populates="incidents_reported",
    )

    resident_profile = db.relationship("ResidentProfile")

    category_rel = db.relationship(
        "IncidentCategory",
        back_populates="incidents",
    )

    location_rel = db.relationship("Location")

    current_authority = db.relationship(
        "Authority",
        back_populates="incidents",
    )

    duplicate_of = db.relationship(
        "Incident",
        remote_side=[id],
        uselist=False,
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

    media = db.relationship(
        "IncidentMedia",
        back_populates="incident",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    assignments = db.relationship(
        "IncidentAssignment",
        back_populates="incident",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Incident id={self.id} status={self.status}>"
