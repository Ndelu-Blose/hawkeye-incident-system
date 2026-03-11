from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.constants import Roles
from app.services.auth_service import auth_service
from app.utils.security import safe_redirect_target
from app.utils.validators import (
    validate_login_form,
    validate_registration_form,
)

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "POST":
        form_data = request.form.to_dict()
        errors = validate_registration_form(form_data)

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("auth/register.html", form_data=form_data)

        user, service_errors = auth_service.register_user(
            name=form_data.get("name", ""),
            email=form_data.get("email", ""),
            password=form_data.get("password", ""),
            role=Roles.RESIDENT.value,
        )

        if service_errors:
            for error in service_errors:
                flash(error, "danger")
            return render_template("auth/register.html", form_data=form_data)

        flash("Registration successful. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "POST":
        form_data = request.form.to_dict()
        errors = validate_login_form(form_data)

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("auth/login.html", form_data=form_data)

        user, service_errors = auth_service.authenticate(
            email=form_data.get("email", ""),
            password=form_data.get("password", ""),
        )

        if service_errors or user is None:
            for error in service_errors or ["Invalid email or password."]:
                flash(error, "danger")
            return render_template("auth/login.html", form_data=form_data)

        login_user(user, remember=True)
        flash("Logged in successfully.", "success")
        return redirect(safe_redirect_target(default=url_for("main.home")))

    return render_template("auth/login.html")


@auth_bp.route("/set-password", methods=["GET", "POST"])
def set_password():
    """Public page: user sets their own password via invite link (admin never sees it)."""
    token = request.args.get("token") or (request.form.get("token") or "").strip()
    if not token and request.method == "GET":
        flash("Invalid or missing link.", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        token = request.form.get("token") or ""
        new_password = (request.form.get("password") or "").strip()
        confirm = (request.form.get("password_confirm") or "").strip()
        if new_password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("auth/set_password.html", token=token)
        ok, errors = auth_service.set_password_by_token(token, new_password)
        if not ok:
            for e in errors:
                flash(e, "danger")
            return render_template("auth/set_password.html", token=token)
        flash("Password set. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/set_password.html", token=token)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.home"))
