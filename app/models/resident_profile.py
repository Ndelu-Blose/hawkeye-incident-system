from __future__ import annotations

from app.extensions import db
from app.utils.datetime_helpers import utc_now


class ResidentProfile(db.Model):
    __tablename__ = "resident_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    phone_number = db.Column(db.String(32))
    street_address_1 = db.Column(db.String(255))
    street_address_2 = db.Column(db.String(255))
    suburb = db.Column(db.String(120))
    city = db.Column(db.String(120))

    municipality_id = db.Column(
        db.Integer,
        db.ForeignKey("locations.id"),
        nullable=True,
    )
    district_id = db.Column(
        db.Integer,
        db.ForeignKey("locations.id"),
        nullable=True,
    )
    ward_id = db.Column(
        db.Integer,
        db.ForeignKey("locations.id"),
        nullable=True,
    )

    postal_code = db.Column(db.String(20))
    latitude = db.Column(db.Numeric(9, 6))
    longitude = db.Column(db.Numeric(9, 6))

    location_verified = db.Column(db.Boolean, nullable=False, default=False)
    profile_completed = db.Column(db.Boolean, nullable=False, default=False)
    consent_location = db.Column(db.Boolean, nullable=False, default=False)
    share_anonymous_analytics = db.Column(db.Boolean, nullable=False, default=False)
    notify_incident_updates = db.Column(db.Boolean, nullable=False, default=True)
    notify_status_changes = db.Column(db.Boolean, nullable=False, default=True)
    notify_community_alerts = db.Column(db.Boolean, nullable=False, default=False)
    avatar_filename = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    user = db.relationship(
        "User",
        back_populates="resident_profile",
    )

    municipality = db.relationship(
        "Location",
        foreign_keys=[municipality_id],
    )
    district = db.relationship(
        "Location",
        foreign_keys=[district_id],
    )
    ward = db.relationship(
        "Location",
        foreign_keys=[ward_id],
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ResidentProfile id={self.id} user_id={self.user_id}>"
