from __future__ import annotations

from app.extensions import db
from app.utils.datetime_helpers import utc_now


class ResidentNotificationState(db.Model):
    __tablename__ = "resident_notification_state"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Last time the resident visited notifications (or marked all read).
    last_seen_at = db.Column(db.DateTime, nullable=False, default=utc_now, index=True)

    user = db.relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ResidentNotificationState user_id={self.user_id}>"
