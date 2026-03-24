from __future__ import annotations

from app.extensions import db
from app.utils.datetime_helpers import utc_now


class Authority(db.Model):
    __tablename__ = "authorities"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(80), unique=True, nullable=True, index=True)
    slug = db.Column(db.String(120), unique=True, nullable=True, index=True)
    authority_type = db.Column(db.String(50))
    contact_email = db.Column(db.String(255))
    contact_phone = db.Column(db.String(50))
    physical_address = db.Column(db.String(255), nullable=True)
    operating_hours = db.Column(db.String(120), nullable=True)
    service_hub = db.Column(db.String(120), nullable=True)
    jurisdiction_notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    routing_enabled = db.Column(db.Boolean, nullable=False, default=True)
    notifications_enabled = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    members = db.relationship(
        "AuthorityUser",
        back_populates="authority",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    incidents = db.relationship(
        "Incident",
        foreign_keys="Incident.current_authority_id",
        back_populates="current_authority",
        lazy="dynamic",
    )

    suggested_incidents = db.relationship(
        "Incident",
        foreign_keys="Incident.suggested_authority_id",
        back_populates="suggested_authority",
        lazy="dynamic",
    )

    assignments = db.relationship(
        "IncidentAssignment",
        back_populates="authority",
        lazy="dynamic",
    )

    routing_rules = db.relationship(
        "RoutingRule",
        back_populates="authority",
        lazy="dynamic",
    )

    dispatches = db.relationship(
        "IncidentDispatch",
        back_populates="authority",
        lazy="dynamic",
    )
    contacts = db.relationship(
        "DepartmentContact",
        back_populates="authority",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    department_action_logs = db.relationship(
        "DepartmentActionLog",
        back_populates="authority",
        lazy="dynamic",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Authority id={self.id} name={self.name!r}>"
