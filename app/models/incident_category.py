from __future__ import annotations

from app.extensions import db
from app.utils.datetime_helpers import utc_now


class IncidentCategory(db.Model):
    __tablename__ = "incident_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    department_hint = db.Column(db.String(150))
    default_priority = db.Column(db.String(32))
    default_sla_hours = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    incidents = db.relationship(
        "Incident",
        back_populates="category_rel",
        lazy="dynamic",
    )

    routing_rules = db.relationship(
        "RoutingRule",
        back_populates="category",
        lazy="dynamic",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<IncidentCategory id={self.id} name={self.name!r}>"
