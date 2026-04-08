from __future__ import annotations

from app.constants import Roles


def validate_email_format(email: str) -> str | None:
    """Return an error message when email format is invalid."""
    value = (email or "").strip()
    if not value:
        return "Email is required."
    if len(value) > 254:
        return "Email is too long."
    if " " in value:
        return "Email must not contain spaces."
    if value.count("@") != 1:
        return "Enter a valid email address."
    local, domain = value.split("@", 1)
    if not local or not domain:
        return "Enter a valid email address."
    if "." not in domain:
        return "Enter a valid email address."
    if domain.startswith(".") or domain.endswith("."):
        return "Enter a valid email address."
    return None


def validate_registration_form(data: dict[str, str]) -> list[str]:
    errors: list[str] = []

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    password_confirm = data.get("password_confirm") or ""

    if not name:
        errors.append("Name is required.")
    email_error = validate_email_format(email)
    if email_error:
        errors.append(email_error)
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if password != password_confirm:
        errors.append("Passwords do not match.")

    return errors


def validate_login_form(data: dict[str, str]) -> list[str]:
    errors: list[str] = []

    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    email_error = validate_email_format(email)
    if email_error:
        errors.append(email_error)
    if not password:
        errors.append("Password is required.")

    return errors


def validate_admin_create_user_form(data: dict[str, str]) -> list[str]:
    """Legacy: admin sets password (avoid for new code; use invite flow)."""
    errors: list[str] = []
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    password_confirm = data.get("password_confirm") or ""
    role = (data.get("role") or "").strip()

    if not name:
        errors.append("Name is required.")
    email_error = validate_email_format(email)
    if email_error:
        errors.append(email_error)
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if password != password_confirm:
        errors.append("Passwords do not match.")

    allowed = {Roles.RESIDENT.value, Roles.AUTHORITY.value, Roles.ADMIN.value}
    if role not in allowed:
        errors.append("Role is invalid.")

    return errors


def validate_admin_create_user_invite(data: dict[str, str]) -> list[str]:
    """Validate name, email, role only; no password (invite flow)."""
    errors: list[str] = []
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    role = (data.get("role") or "").strip()

    if not name:
        errors.append("Name is required.")
    email_error = validate_email_format(email)
    if email_error:
        errors.append(email_error)

    allowed = {Roles.RESIDENT.value, Roles.AUTHORITY.value, Roles.ADMIN.value}
    if role not in allowed:
        errors.append("Role is invalid.")

    return errors


def validate_admin_update_user_form(data: dict[str, str]) -> list[str]:
    errors: list[str] = []
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    role = (data.get("role") or "").strip()

    if not name:
        errors.append("Name is required.")
    email_error = validate_email_format(email)
    if email_error:
        errors.append(email_error)

    allowed = {Roles.RESIDENT.value, Roles.AUTHORITY.value, Roles.ADMIN.value}
    if role not in allowed:
        errors.append("Role is invalid.")

    return errors
