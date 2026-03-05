from __future__ import annotations

from app.constants import Roles
from app.extensions import db
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.utils.security import check_password, hash_password


class AuthService:
    """Authentication and registration workflows."""

    def __init__(self, user_repo: UserRepository | None = None) -> None:
        self.user_repo = user_repo or UserRepository()

    def register_user(
        self,
        name: str,
        email: str,
        password: str,
        role: str = Roles.RESIDENT.value,
    ) -> tuple[User | None, list[str]]:
        errors: list[str] = []

        existing = self.user_repo.get_by_email(email)
        if existing:
            errors.append("An account with that email already exists.")
            return None, errors

        user = User(
            name=name.strip(),
            email=email.strip().lower(),
            password_hash=hash_password(password),
            role=role,
        )
        self.user_repo.add(user)
        db.session.commit()
        return user, errors

    def authenticate(
        self,
        email: str,
        password: str,
    ) -> tuple[User | None, list[str]]:
        errors: list[str] = []
        user = self.user_repo.get_by_email(email.strip().lower())
        if user is None:
            errors.append("Invalid email or password.")
            return None, errors

        if not check_password(password, user.password_hash):
            errors.append("Invalid email or password.")
            return None, errors

        return user, errors


auth_service = AuthService()
