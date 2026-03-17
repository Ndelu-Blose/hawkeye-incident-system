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

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<IncidentDispatch id={self.id} incident_id={self.incident_id} "
            f"authority_id={self.authority_id}>"
        )
