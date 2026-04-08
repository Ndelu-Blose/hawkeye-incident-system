from __future__ import annotations

from app.extensions import db
from app.utils.datetime_helpers import utc_now


class RoutingRule(db.Model):
    __tablename__ = "routing_rules"

    id = db.Column(db.Integer, primary_key=True)

    category_id = db.Column(
        db.Integer,
        db.ForeignKey("incident_categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    location_id = db.Column(
        db.Integer,
        db.ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=True,
    )
    authority_id = db.Column(
        db.Integer,
        db.ForeignKey("authorities.id", ondelete="CASCADE"),
        nullable=False,
    )

    priority_override = db.Column(db.String(32))
    sla_hours_override = db.Column(db.Integer)
    priority = db.Column(db.Integer, nullable=False, default=100, index=True)
    effective_from = db.Column(db.DateTime, nullable=True, index=True)
    effective_to = db.Column(db.DateTime, nullable=True, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    category = db.relationship(
        "IncidentCategory",
        back_populates="routing_rules",
    )
    location = db.relationship("Location")
    authority = db.relationship(
        "Authority",
        back_populates="routing_rules",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<RoutingRule id={self.id} category_id={self.category_id} "
            f"location_id={self.location_id} authority_id={self.authority_id}>"
        )
