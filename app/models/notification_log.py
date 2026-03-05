from __future__ import annotations

from datetime import datetime

from app.extensions import db


class NotificationLog(db.Model):
    __tablename__ = "notification_log"

    id = db.Column(db.Integer, primary_key=True)

    incident_id = db.Column(
        db.Integer,
        db.ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Either store a foreign key to the user or just an email address
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    recipient_email = db.Column(db.String(255), nullable=True)

    type = db.Column(db.String(64), nullable=False)  # e.g. incident_created, status_changed
    status = db.Column(db.String(32), nullable=False, default="queued", index=True)

    provider_message_id = db.Column(db.String(255), nullable=True)
    last_error = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    sent_at = db.Column(db.DateTime, nullable=True)

    incident = db.relationship(
        "Incident",
        back_populates="notifications",
    )

    user = db.relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<NotificationLog id={self.id} status={self.status}>"
