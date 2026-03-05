from __future__ import annotations

from app.extensions import db
from app.models.user import User


class UserRepository:
    """Data access helper for User entities."""

    def get_by_id(self, user_id: int) -> User | None:
        return db.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return User.query.filter_by(email=email).one_or_none()

    def add(self, user: User) -> User:
        db.session.add(user)
        return user

    def commit(self) -> None:
        db.session.commit()
