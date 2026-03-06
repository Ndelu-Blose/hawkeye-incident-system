from __future__ import annotations

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user

from app.constants import Roles

main_bp = Blueprint("main", __name__)


def _role_value(value: object) -> str:
    raw = getattr(value, "value", value)
    if raw is None:
        return ""
    return str(raw).strip().lower()


@main_bp.route("/")
def home():
    if current_user.is_authenticated:
        role = _role_value(getattr(current_user, "role", ""))

        if role == Roles.RESIDENT.value:
            return redirect(url_for("resident.dashboard"))
        if role == Roles.AUTHORITY.value:
            return redirect(url_for("authority.dashboard"))
        if role == Roles.ADMIN.value:
            return redirect(url_for("admin.dashboard"))

    return render_template("home.html")
