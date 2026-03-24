"""Incident dispatch records: proof of dispatch and delivery to departments."""

from __future__ import annotations

from app.extensions import db
from app.utils.datetime_helpers import utc_now


class IncidentDispatch(db.Model):
    """Records each dispatch of an incident to a department (assignment-level)."""

    __tablename__ = "incident_dispatches"

    id = db.Column(db.Integer, primary_key=True)

    incident_assignment_id = db.Column(
        db.Integer,
        db.ForeignKey("incident_assignments.id", ondelete="CASCADE"),
        nullable=False,
    )
    incident_id = db.Column(
        db.Integer,
        db.ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    authority_id = db.Column(
        db.Integer,
        db.ForeignKey("authorities.id", ondelete="CASCADE"),
        nullable=False,
    )

    dispatch_method = db.Column(
        db.String(32),
        nullable=False,
        default="internal_queue",
    )  # internal_queue | email | sms | api
    dispatched_by_type = db.Column(
        db.String(32),
        nullable=False,
    )  # admin | system
    dispatched_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    destination_reference = db.Column(db.String(255), nullable=True)
    delivery_status = db.Column(
        db.String(32),
        nullable=False,
        default="pending",
    )  # pending | sent | delivered | failed
    delivery_status_detail = db.Column(db.Text, nullable=True)

    ack_status = db.Column(
        db.String(32),
        nullable=False,
        default="pending",
    )  # pending | acknowledged | rejected
    ack_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    ack_at = db.Column(db.DateTime, nullable=True)

    dispatched_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    delivery_confirmed_at = db.Column(db.DateTime, nullable=True)
    # Operational dispatch lifecycle (new backbone fields).
    status = db.Column(db.String(30), nullable=False, default="pending", index=True)
    recipient_email = db.Column(db.String(255), nullable=True)
    subject_snapshot = db.Column(db.String(255), nullable=True)
    message_snapshot = db.Column(db.Text, nullable=True)
    delivery_provider = db.Column(db.String(64), nullable=True)
    delivery_reference = db.Column(db.String(255), nullable=True)
    failure_reason = db.Column(db.Text, nullable=True)
    external_reference_number = db.Column(db.String(120), nullable=True)
    external_reference_source = db.Column(db.String(120), nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    acknowledged_by = db.Column(db.String(255), nullable=True)
    resolution_note = db.Column(db.Text, nullable=True)
    resolution_proof_url = db.Column(db.String(512), nullable=True)
    last_status_update_at = db.Column(db.DateTime, nullable=True)
    reminder_count = db.Column(db.Integer, nullable=False, default=0)
    last_reminder_at = db.Column(db.DateTime, nullable=True)
    next_reminder_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    assignment = db.relationship(
        "IncidentAssignment",
        back_populates="dispatches",
    )
    incident = db.relationship("Incident", back_populates="dispatches")
    authority = db.relationship("Authority", back_populates="dispatches")
    dispatcher = db.relationship(
        "User",
        foreign_keys=[dispatched_by_id],
    )
    ack_user = db.relationship(
        "User",
        foreign_keys=[ack_user_id],
    )

    @property
    def channel(self) -> str:
        return self.dispatch_method

    @channel.setter
    def channel(self, value: str) -> None:
        self.dispatch_method = value

    @property
    def sent_at(self):
        return self.dispatched_at

    @sent_at.setter
    def sent_at(self, value) -> None:
        self.dispatched_at = value

    @property
    def acknowledged_at(self):
        return self.ack_at

    @acknowledged_at.setter
    def acknowledged_at(self, value) -> None:
        self.ack_at = value

    @property
    def created_by_user_id(self):
        return self.dispatched_by_id

    @created_by_user_id.setter
    def created_by_user_id(self, value) -> None:
        self.dispatched_by_id = value

    @property
    def department_id(self):
        return self.authority_id

    @department_id.setter
    def department_id(self, value) -> None:
        self.authority_id = value

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<IncidentDispatch id={self.id} incident_id={self.incident_id} "
            f"authority_id={self.authority_id}>"
        )
