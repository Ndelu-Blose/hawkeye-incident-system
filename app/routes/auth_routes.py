from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
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
            email_verified=False,
        )

        if service_errors:
            for error in service_errors:
                flash(error, "danger")
            return render_template("auth/register.html", form_data=form_data)

        if user is None:
            flash("Registration failed. Please try again.", "danger")
            return render_template("auth/register.html", form_data=form_data)

        try:
            send_ok, send_errors = auth_service.send_verification_email(user)
        except Exception:
            current_app.logger.exception("send_verification_email failed after registration")
            flash(
                "Your account was created, but we could not send the verification email. "
                "Use Resend verification on the sign-in page after you set APP_BASE_URL and Resend, "
                "or check server logs.",
                "warning",
            )
            return redirect(url_for("auth.login"))

        if not send_ok:
            for err in send_errors:
                flash(err, "warning")
        flash(
            "Account created. We sent a verification link to your email. "
            "Confirm your address, then sign in.",
            "success",
        )
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

        try:
            user, service_errors = auth_service.authenticate(
                email=form_data.get("email", ""),
                password=form_data.get("password", ""),
            )
        except Exception:
            current_app.logger.exception("login: unexpected error during authenticate")
            flash(
                "We could not complete sign-in. Try again, or contact support if it keeps happening.",
                "danger",
            )
            return render_template("auth/login.html", form_data=form_data)

        if service_errors or user is None:
            for error in service_errors or ["Invalid email or password."]:
                flash(error, "danger")
            return render_template("auth/login.html", form_data=form_data)

        try:
            login_user(user, remember=True)
        except Exception:
            current_app.logger.exception(
                "login: login_user failed for user id=%s", getattr(user, "id", None)
            )
            flash(
                "We could not start your session. Clear site cookies for this host and try again.",
                "danger",
            )
            return render_template("auth/login.html", form_data=form_data)

        flash("Logged in successfully.", "success")
        return redirect(safe_redirect_target(default=url_for("main.home")))

    return render_template("auth/login.html", form_data=None)


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


@auth_bp.route("/verify-email", methods=["GET"])
def verify_email():
    token = (request.args.get("token") or "").strip()
    ok, errors = auth_service.verify_email_token(token)
    if ok:
        flash("Your email is verified. You can sign in now.", "success")
        return redirect(url_for("auth.login"))
    for err in errors:
        flash(err, "danger")
    return redirect(url_for("auth.login"))


@auth_bp.route("/resend-verification", methods=["GET", "POST"])
def resend_verification():
    if request.method == "POST":
        form_data = request.form.to_dict()
        email = form_data.get("email", "")
        try:
            ok, errors = auth_service.request_verification_resend(email)
        except Exception:
            current_app.logger.exception("resend_verification route failed")
            ok, errors = (
                False,
                ["Could not process verification resend right now. Please try again shortly."],
            )
        if not ok:
            for err in errors:
                flash(err, "danger")
            return render_template(
                "auth/resend_verification.html",
                form_data=form_data,
            )
        flash(
            "If an account exists for that address and still needs verification, "
            "we sent a new email.",
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/resend_verification.html")


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    if request.method == "POST":
        form_data = request.form.to_dict()
        email = form_data.get("email", "")
        ok, errors = auth_service.request_password_reset_by_email(email)
        if not ok:
            for err in errors:
                flash(err, "danger")
            return render_template("auth/forgot_password.html", form_data=form_data)
        flash(
            "If an account exists for that address, we sent password reset instructions.",
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.home"))
