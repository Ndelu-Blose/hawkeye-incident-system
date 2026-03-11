from __future__ import annotations

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user

from app.constants import Roles
from app.extensions import db
from app.models.admin_preference import AdminPreference

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
            prefs = (
                db.session.query(AdminPreference)
                .filter(AdminPreference.user_id == getattr(current_user, "id", 0))
                .first()
            )
            landing = (prefs.default_landing_page if prefs else "dashboard") or "dashboard"
            endpoint_map = {
                "dashboard": "admin.dashboard",
                "incidents": "admin.incidents",
                "users": "admin.users",
                "authorities": "admin.authorities",
                "routing_rules": "admin.routing_rules",
            }
            return redirect(url_for(endpoint_map.get(landing, "admin.dashboard")))

    return render_template("home.html")
