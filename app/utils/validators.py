from __future__ import annotations

from app.constants import Roles


def validate_registration_form(data: dict[str, str]) -> list[str]:
    errors: list[str] = []

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    password_confirm = data.get("password_confirm") or ""

    if not name:
        errors.append("Name is required.")
    if not email:
        errors.append("Email is required.")
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if password != password_confirm:
        errors.append("Passwords do not match.")

    return errors


def validate_login_form(data: dict[str, str]) -> list[str]:
    errors: list[str] = []

    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if not email:
        errors.append("Email is required.")
    if not password:
        errors.append("Password is required.")

    return errors


def validate_admin_create_user_form(data: dict[str, str]) -> list[str]:
    errors: list[str] = []
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    password_confirm = data.get("password_confirm") or ""
    role = (data.get("role") or "").strip()

    if not name:
        errors.append("Name is required.")
    if not email:
        errors.append("Email is required.")
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if password != password_confirm:
        errors.append("Passwords do not match.")

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
    if not email:
        errors.append("Email is required.")

    allowed = {Roles.RESIDENT.value, Roles.AUTHORITY.value, Roles.ADMIN.value}
    if role not in allowed:
        errors.append("Role is invalid.")

    return errors
