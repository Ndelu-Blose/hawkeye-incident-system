from __future__ import annotations

from app.extensions import db
from app.utils.datetime_helpers import utc_now


class AuthorityUser(db.Model):
    __tablename__ = "authority_users"

    id = db.Column(db.Integer, primary_key=True)

    authority_id = db.Column(
        db.Integer,
        db.ForeignKey("authorities.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    job_title = db.Column(db.String(120))
    can_assign = db.Column(db.Boolean, nullable=False, default=False)
    can_resolve = db.Column(db.Boolean, nullable=False, default=False)
    can_export = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    authority = db.relationship(
        "Authority",
        back_populates="members",
    )
    user = db.relationship(
        "User",
        back_populates="authority_memberships",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<AuthorityUser id={self.id} authority_id={self.authority_id} user_id={self.user_id}>"
        )
