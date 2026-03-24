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
    additional_notes = db.Column(db.Text, nullable=True)
    dynamic_details = db.Column(db.JSON, nullable=True)
    category = db.Column(db.String(100), nullable=False)

    category_id = db.Column(
        db.Integer,
        db.ForeignKey("incident_categories.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Screening & routing insight fields
    resident_category_id = db.Column(
        db.Integer,
        db.ForeignKey("incident_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    system_category_id = db.Column(
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
    # Phase 2 structured / validated location metadata
    validated_address = db.Column(db.String(255), nullable=True)
    suburb = db.Column(db.String(120), nullable=True)
    ward = db.Column(db.String(64), nullable=True)
    location_validated = db.Column(db.Boolean, nullable=False, default=False)

    location_id = db.Column(
        db.Integer,
        db.ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    latitude = db.Column(db.Numeric(9, 6), nullable=True)
    longitude = db.Column(db.Numeric(9, 6), nullable=True)
    location_precision = db.Column(db.String(32), nullable=True)
    geocoded_at = db.Column(db.DateTime, nullable=True)
    geocode_source = db.Column(db.String(64), nullable=True)
    hotspot_excluded = db.Column(db.Boolean, nullable=False, default=False)

    severity = db.Column(db.String(50), nullable=False)

    status = db.Column(
        db.String(32),
        nullable=False,
        default=IncidentStatus.REPORTED.value,
        index=True,
    )

    # Optional optimistic concurrency field
    version = db.Column(db.Integer, nullable=False, default=1)

    reference_code = db.Column(
        db.String(32),
        nullable=False,
        unique=True,
        index=True,
    )

    current_authority_id = db.Column(
        db.Integer,
        db.ForeignKey("authorities.id", ondelete="SET NULL"),
        nullable=True,
    )

    suggested_authority_id = db.Column(
        db.Integer,
        db.ForeignKey("authorities.id", ondelete="SET NULL"),
        nullable=True,
    )

    suggested_priority = db.Column(db.String(50), nullable=True)
    screening_confidence = db.Column(db.Float, nullable=True)
    requires_admin_review = db.Column(db.Boolean, nullable=False, default=False)
    screening_notes = db.Column(db.Text, nullable=True)
    verification_status = db.Column(db.String(32), nullable=False, default="pending", index=True)
    verification_notes = db.Column(db.Text, nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    verified_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    proof_requested_at = db.Column(db.DateTime, nullable=True)
    proof_requested_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    proof_request_reason = db.Column(db.Text, nullable=True)
    evidence_resubmitted_at = db.Column(db.DateTime, nullable=True)
    escalated_at = db.Column(db.DateTime, nullable=True)
    escalated_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
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

    # Guided incident wizard fields
    location_mode = db.Column(db.String(32), nullable=True)  # saved | current | other
    is_happening_now = db.Column(db.Boolean, nullable=True)
    is_anyone_in_danger = db.Column(db.Boolean, nullable=True)
    is_issue_still_present = db.Column(db.Boolean, nullable=True)
    urgency_level = db.Column(db.String(32), nullable=True)  # urgent_now | soon | scheduled

    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    reporter = db.relationship(
        "User",
        back_populates="incidents_reported",
        foreign_keys=[reported_by_id],
    )
    verified_by = db.relationship("User", foreign_keys=[verified_by_user_id])
    proof_requested_by = db.relationship("User", foreign_keys=[proof_requested_by_user_id])
    escalated_by = db.relationship("User", foreign_keys=[escalated_by_user_id])

    resident_profile = db.relationship("ResidentProfile")

    category_rel = db.relationship(
        "IncidentCategory",
        foreign_keys=[category_id],
        back_populates="incidents",
    )

    location_rel = db.relationship("Location")

    current_authority = db.relationship(
        "Authority",
        foreign_keys=[current_authority_id],
        back_populates="incidents",
    )

    suggested_authority = db.relationship(
        "Authority",
        foreign_keys=[suggested_authority_id],
        back_populates="suggested_incidents",
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

    dispatches = db.relationship(
        "IncidentDispatch",
        back_populates="incident",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    department_action_logs = db.relationship(
        "DepartmentActionLog",
        back_populates="incident",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    incident_events = db.relationship(
        "IncidentEvent",
        back_populates="incident",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="IncidentEvent.created_at",
    )

    ownership_history = db.relationship(
        "IncidentOwnershipHistory",
        back_populates="incident",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Incident id={self.id} status={self.status}>"
