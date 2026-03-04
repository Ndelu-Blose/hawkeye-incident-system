from __future__ import annotations

from datetime import datetime

from flask_login import UserMixin

from app.constants import Roles
from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False, default=Roles.RESIDENT.value)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    incidents_reported = db.relationship(
        "Incident",
        back_populates="reporter",
        lazy="dynamic",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug representation
        return f"<User id={self.id} email={self.email} role={self.role}>"

