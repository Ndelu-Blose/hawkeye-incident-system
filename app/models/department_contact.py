from __future__ import annotations

from app.extensions import db
from app.utils.datetime_helpers import utc_now


class DepartmentContact(db.Model):
    __tablename__ = "department_contacts"

    id = db.Column(db.Integer, primary_key=True)
    authority_id = db.Column(
        db.Integer,
        db.ForeignKey("authorities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_type = db.Column(db.String(24), nullable=False, default="primary")
    is_primary = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_secondary = db.Column(db.Boolean, nullable=False, default=False, index=True)
    channel = db.Column(db.String(24), nullable=False)
    value = db.Column(db.String(255), nullable=False)
    verification_status = db.Column(db.String(24), nullable=False, default="unverified", index=True)
    source_url = db.Column(db.String(512), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    after_hours = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    authority = db.relationship("Authority", back_populates="contacts")

    __table_args__ = (
        db.UniqueConstraint(
            "authority_id",
            "contact_type",
            "channel",
            "value",
            name="uq_department_contact_per_authority",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DepartmentContact id={self.id} authority_id={self.authority_id}>"
