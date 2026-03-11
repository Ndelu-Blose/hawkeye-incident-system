from __future__ import annotations

from app.extensions import db
from app.utils.datetime_helpers import utc_now


class AdminPreference(db.Model):
    __tablename__ = "admin_preferences"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Overview (dashboard) widgets
    show_kpi_cards = db.Column(db.Boolean, nullable=False, default=True)
    show_recent_incidents = db.Column(db.Boolean, nullable=False, default=True)
    show_overdue_panel = db.Column(db.Boolean, nullable=False, default=True)
    show_user_stats = db.Column(db.Boolean, nullable=False, default=True)

    # Notifications (email)
    notify_new_incident = db.Column(db.Boolean, nullable=False, default=False)
    notify_overdue_incident = db.Column(db.Boolean, nullable=False, default=False)
    daily_summary_enabled = db.Column(db.Boolean, nullable=False, default=False)

    # Defaults
    default_landing_page = db.Column(db.String(32), nullable=False, default="dashboard")
    default_incident_sort = db.Column(db.String(32), nullable=False, default="newest")
    default_rows_per_page = db.Column(db.Integer, nullable=False, default=25)

    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    user = db.relationship("User")
