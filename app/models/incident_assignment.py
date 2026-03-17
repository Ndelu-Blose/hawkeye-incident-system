from __future__ import annotations

from app.extensions import db
from app.utils.datetime_helpers import utc_now


class IncidentAssignment(db.Model):
    __tablename__ = "incident_assignments"

    id = db.Column(db.Integer, primary_key=True)

    incident_id = db.Column(
        db.Integer,
        db.ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    authority_id = db.Column(
        db.Integer,
        db.ForeignKey("authorities.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_to_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    assignment_reason = db.Column(db.Text)
    assigned_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    unassigned_at = db.Column(db.DateTime)

    incident = db.relationship(
        "Incident",
        back_populates="assignments",
    )
    authority = db.relationship(
        "Authority",
        back_populates="assignments",
    )
    assignee = db.relationship(
        "User",
        foreign_keys=[assigned_to_user_id],
    )
    assigner = db.relationship(
        "User",
        foreign_keys=[assigned_by_user_id],
    )

    dispatches = db.relationship(
        "IncidentDispatch",
        back_populates="assignment",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<IncidentAssignment id={self.id} "
            f"incident_id={self.incident_id} authority_id={self.authority_id}>"
        )
