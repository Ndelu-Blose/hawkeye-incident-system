from __future__ import annotations

from app.extensions import db
from app.utils.datetime_helpers import utc_now


class Location(db.Model):
    __tablename__ = "locations"

    id = db.Column(db.Integer, primary_key=True)

    country = db.Column(db.String(100))
    province = db.Column(db.String(100))
    municipality = db.Column(db.String(150))
    district = db.Column(db.String(150))
    ward = db.Column(db.String(50))
    suburb = db.Column(db.String(150))
    area_name = db.Column(db.String(255))
    boundary_geojson = db.Column(db.Text)

    parent_location_id = db.Column(
        db.Integer,
        db.ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    parent = db.relationship(
        "Location",
        remote_side=[id],
        backref="children",
    )

    @property
    def name(self) -> str:
        """Human-friendly label for templates and dropdowns."""
        for value in (
            self.area_name,
            self.suburb,
            self.ward,
            self.municipality,
            self.district,
            self.province,
            self.country,
        ):
            if value:
                return str(value).strip()
        return f"Location #{self.id}"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Location id={self.id} area={self.area_name!r}>"
