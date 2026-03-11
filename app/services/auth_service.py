from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from flask import current_app, url_for
from flask_mail import Message

from app.constants import Roles
from app.extensions import db, mail
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

    def create_user_invite(
        self,
        name: str,
        email: str,
        role: str = Roles.RESIDENT.value,
        expires_in_days: int = 7,
    ) -> tuple[User | None, str | None, list[str]]:
        """Create a user with no password; they must set it via the invite link.
        Returns (user, invite_token, errors). Admin never sees or sets a password.
        """
        errors: list[str] = []
        existing = self.user_repo.get_by_email(email.strip().lower())
        if existing:
            errors.append("An account with that email already exists.")
            return None, None, errors

        # Random hash so the account cannot be used until the user sets a password
        random_password = secrets.token_urlsafe(32)
        user = User(
            name=name.strip(),
            email=email.strip().lower(),
            password_hash=hash_password(random_password),
            role=role,
            invite_token=secrets.token_urlsafe(32),
            invite_expires_at=datetime.now(UTC) + timedelta(days=expires_in_days),
        )
        self.user_repo.add(user)
        db.session.commit()
        return user, user.invite_token, []

    def create_set_password_token(
        self,
        user: User,
        *,
        expires_in_days: int = 7,
    ) -> tuple[str, datetime]:
        """Create/refresh a one-time set-password token for a user."""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)
        user.invite_token = token
        user.invite_expires_at = expires_at
        db.session.commit()
        return token, expires_at

    def send_password_reset_email(self, user: User) -> tuple[bool, list[str]]:
        """Email a set-password link to the user (production-safe reset)."""
        errors: list[str] = []
        if not user.email:
            return False, ["User has no email address on file."]

        token, expires_at = self.create_set_password_token(user, expires_in_days=7)
        reset_url = url_for("auth.set_password", token=token, _external=True)

        subject = "Alertweb Solutions password reset"
        body = (
            "A password reset was requested for your Alertweb Solutions account.\n\n"
            f"Set your new password using this link (expires {expires_at.date()}):\n"
            f"{reset_url}\n\n"
            "If you did not request this, you can ignore this email."
        )

        try:
            msg = Message(
                subject=subject,
                recipients=[user.email],
                body=body,
            )
            mail.send(msg)
            return True, []
        except Exception:
            # Graceful fallback: in dev, surface the link so admins can continue demos.
            if current_app.config.get("ENV") != "production":
                errors.append(
                    f"Email sending is not configured. Dev reset link for {user.email}: {reset_url}"
                )
            else:
                errors.append("Email sending failed. Please configure mail settings and try again.")
            return False, errors

    def set_password_by_token(self, token: str, new_password: str) -> tuple[bool, list[str]]:
        """Consume an invite token and set the user's password. Token is invalidated."""
        errors: list[str] = []
        if not token or not new_password:
            errors.append("Invalid or expired link.")
            return False, errors
        if len(new_password) < 8:
            errors.append("Password must be at least 8 characters.")
            return False, errors

        user = (
            db.session.query(User)
            .filter(
                User.invite_token == token,
                User.invite_expires_at.isnot(None),
                User.invite_expires_at > datetime.now(UTC),
            )
            .first()
        )
        if user is None:
            errors.append("This link has expired or is invalid.")
            return False, errors

        user.password_hash = hash_password(new_password)
        user.invite_token = None
        user.invite_expires_at = None
        db.session.commit()
        return True, []

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
