from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app.constants import Roles
from app.extensions import db
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.services.resend_email import send_outbound_email
from app.utils.datetime_helpers import is_past_utc, utc_now_naive
from app.utils.public_urls import public_url_for
from app.utils.security import check_password, hash_password
from app.utils.validators import validate_email_format


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
        *,
        email_verified: bool = False,
    ) -> tuple[User | None, list[str]]:
        errors: list[str] = []
        normalized_email = email.strip().lower()
        email_error = validate_email_format(normalized_email)
        if email_error:
            errors.append(email_error)
            return None, errors

        existing = self.user_repo.get_by_email(normalized_email)
        if existing:
            errors.append("An account with that email already exists.")
            return None, errors

        user = User(
            name=name.strip(),
            email=normalized_email,
            password_hash=hash_password(password),
            role=role,
            email_verified=email_verified,
        )
        if not email_verified:
            self._set_email_verification_token(user)
        self.user_repo.add(user)
        db.session.commit()
        return user, errors

    def _set_email_verification_token(self, user: User) -> None:
        days = int(current_app.config.get("EMAIL_VERIFICATION_TOKEN_DAYS", 7))
        user.email_verification_token = secrets.token_urlsafe(32)
        user.email_verification_expires_at = utc_now_naive() + timedelta(days=days)

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
        normalized_email = email.strip().lower()
        email_error = validate_email_format(normalized_email)
        if email_error:
            errors.append(email_error)
            return None, None, errors
        existing = self.user_repo.get_by_email(normalized_email)
        if existing:
            errors.append("An account with that email already exists.")
            return None, None, errors

        # Random hash so the account cannot be used until the user sets a password
        random_password = secrets.token_urlsafe(32)
        user = User(
            name=name.strip(),
            email=normalized_email,
            password_hash=hash_password(random_password),
            role=role,
            email_verified=True,
            invite_token=secrets.token_urlsafe(32),
            invite_expires_at=utc_now_naive() + timedelta(days=expires_in_days),
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
        expires_at = utc_now_naive() + timedelta(days=expires_in_days)
        user.invite_token = token
        user.invite_expires_at = expires_at
        db.session.commit()
        return token, expires_at

    def request_password_reset_by_email(self, email: str) -> tuple[bool, list[str]]:
        """Look up user by email and send a reset link. Returns same shape as send_password_reset_email."""
        normalized = email.strip().lower()
        email_error = validate_email_format(normalized)
        if email_error:
            return False, [email_error]
        user = self.user_repo.get_by_email(normalized)
        if user is None:
            return True, []
        return self.send_password_reset_email(user)

    def send_password_reset_email(self, user: User) -> tuple[bool, list[str]]:
        """Email a set-password link to the user (production-safe reset)."""
        errors: list[str] = []
        if not user.email:
            return False, ["User has no email address on file."]

        token, expires_at = self.create_set_password_token(user, expires_in_days=7)
        reset_url = public_url_for("auth.set_password", token=token)

        subject = "Alertweb Solutions password reset"
        body = (
            "A password reset was requested for your Alertweb Solutions account.\n\n"
            f"Set your new password using this link (expires {expires_at.date()}):\n"
            f"{reset_url}\n\n"
            "If you did not request this, you can ignore this email."
        )
        html = (
            "<p>A password reset was requested for your Alertweb Solutions account.</p>"
            f"<p>Set your new password using this link (expires {expires_at.date()}):</p>"
            f'<p><a href="{reset_url}">Reset password</a></p>'
            "<p>If you did not request this, you can ignore this email.</p>"
        )

        try:
            ok, detail, _provider = send_outbound_email(
                current_app,
                to_email=user.email,
                subject=subject,
                text_body=body,
                html_body=html,
            )
        except Exception as exc:
            current_app.logger.exception(
                "send_verification_email: provider failure for %s",
                user.email,
            )
            ok, detail = False, str(exc)
        if ok:
            return True, []

        if current_app.config.get("ENV") != "production":
            errors.append(
                "Email could not be sent automatically. "
                f"Dev reset link for {user.email}: {reset_url}"
            )
            if detail:
                errors.append(f"Detail: {detail}")
        else:
            errors.append(
                "Could not send password reset email. "
                "Configure Resend (RESEND_API_KEY, RESEND_FROM_EMAIL) or SMTP mail settings."
            )
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

        now_naive = utc_now_naive()
        user = (
            db.session.query(User)
            .filter(
                User.invite_token == token,
                User.invite_expires_at.isnot(None),
                User.invite_expires_at > now_naive,
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
        normalized_email = email.strip().lower()
        email_error = validate_email_format(normalized_email)
        if email_error:
            errors.append("Invalid email or password.")
            return None, errors
        try:
            user = self.user_repo.get_by_email(normalized_email)
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("authenticate: database error for %s", normalized_email)
            return None, [
                "Sign-in is temporarily unavailable. "
                "If this continues, ask an admin to run database migrations (flask db upgrade).",
            ]
        if user is None:
            errors.append("Invalid email or password.")
            return None, errors

        if not user.is_active:
            errors.append("This account is no longer active.")
            return None, errors

        try:
            password_ok = check_password(password, user.password_hash)
        except (TypeError, ValueError) as exc:
            current_app.logger.warning(
                "authenticate: password check error for %s: %s",
                normalized_email,
                exc,
            )
            errors.append("Invalid email or password.")
            return None, errors
        if not password_ok:
            errors.append("Invalid email or password.")
            return None, errors

        if not user.email_verified and current_app.config.get(
            "EMAIL_VERIFICATION_REQUIRED",
            True,
        ):
            errors.append(
                "Please verify your email before signing in. "
                "Check your inbox or use Resend verification below."
            )
            return None, errors

        return user, errors

    def send_verification_email(self, user: User) -> tuple[bool, list[str]]:
        """Send a Resend email with a link to confirm the address."""
        errors: list[str] = []
        if not user.email:
            return False, ["User has no email address on file."]
        if user.email_verified:
            return True, []

        if not user.email_verification_token or is_past_utc(user.email_verification_expires_at):
            self._set_email_verification_token(user)
            db.session.commit()

        verify_url = public_url_for("auth.verify_email", token=user.email_verification_token)
        exp = user.email_verification_expires_at
        exp_label = exp.date().isoformat() if exp is not None else "see link"
        subject = "Verify your Alertweb Solutions email"
        body = (
            "Thanks for registering with Alertweb Solutions.\n\n"
            "Confirm your email address by opening this link "
            f"(expires {exp_label}):\n"
            f"{verify_url}\n\n"
            "If you did not create an account, you can ignore this email."
        )
        html = (
            "<p>Thanks for registering with Alertweb Solutions.</p>"
            "<p>Confirm your email address by clicking the link below "
            f"(expires {exp_label}):</p>"
            f'<p><a href="{verify_url}">Verify email address</a></p>'
            "<p>If you did not create an account, you can ignore this email.</p>"
        )

        try:
            ok, detail, _provider = send_outbound_email(
                current_app,
                to_email=user.email,
                subject=subject,
                text_body=body,
                html_body=html,
            )
        except Exception as exc:
            current_app.logger.exception(
                "send_verification_email failed for user_id=%s",
                getattr(user, "id", None),
            )
            ok, detail = False, str(exc)
        if ok:
            return True, []

        if current_app.config.get("ENV") != "production":
            errors.append(
                "Email could not be sent automatically. "
                f"Dev verification link for {user.email}: {verify_url}"
            )
            if detail:
                errors.append(f"Detail: {detail}")
        else:
            errors.append(
                "Could not send verification email. "
                "Configure Resend (RESEND_API_KEY, RESEND_FROM_EMAIL) or SMTP mail settings."
            )
        return False, errors

    def verify_email_token(self, token: str) -> tuple[bool, list[str]]:
        """Mark the user's email verified when the token matches and is still valid."""
        errors: list[str] = []
        if not token or not token.strip():
            errors.append("Invalid or missing verification link.")
            return False, errors
        token = token.strip()
        now_naive = utc_now_naive()
        user = (
            db.session.query(User)
            .filter(
                User.email_verification_token == token,
                User.email_verification_expires_at.isnot(None),
                User.email_verification_expires_at > now_naive,
            )
            .first()
        )
        if user is None:
            errors.append("This verification link has expired or is invalid.")
            return False, errors

        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_expires_at = None
        db.session.commit()
        return True, []

    def request_verification_resend(self, email: str) -> tuple[bool, list[str]]:
        """Resend verification for an unverified account (anti-enumeration: generic messages)."""
        errors: list[str] = []
        normalized = email.strip().lower()
        email_error = validate_email_format(normalized)
        if email_error:
            errors.append(email_error)
            return False, errors

        try:
            user = self.user_repo.get_by_email(normalized)
        except SQLAlchemyError:
            db.session.rollback()
            return False, [
                "Could not process verification resend right now. Please try again shortly."
            ]
        if user is None or user.email_verified:
            return True, []

        try:
            ok, send_errors = self.send_verification_email(user)
        except Exception:
            current_app.logger.exception(
                "request_verification_resend failed for email=%s", normalized
            )
            return False, ["Could not send verification email right now. Please try again shortly."]
        if not ok:
            return False, send_errors
        return True, []


auth_service = AuthService()
