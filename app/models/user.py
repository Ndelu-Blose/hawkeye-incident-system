from __future__ import annotations

from flask_login import UserMixin

from app.constants import Roles
from app.extensions import db
from app.utils.datetime_helpers import utc_now


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False, default=Roles.RESIDENT.value)

    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    phone_verified = db.Column(db.Boolean, nullable=False, default=False)
    last_login_at = db.Column(db.DateTime, nullable=True)

    # Invite flow: one-time token for user to set their own password (admin never sees it)
    invite_token = db.Column(db.String(64), nullable=True, index=True)
    invite_expires_at = db.Column(db.DateTime, nullable=True)

    incidents_reported = db.relationship(
        "Incident",
        back_populates="reporter",
        foreign_keys="Incident.reported_by_id",
        lazy="dynamic",
    )

    resident_profile = db.relationship(
        "ResidentProfile",
        back_populates="user",
        uselist=False,
    )

    authority_memberships = db.relationship(
        "AuthorityUser",
        back_populates="user",
        lazy="dynamic",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug representation
        return f"<User id={self.id} email={self.email} role={self.role}>"
