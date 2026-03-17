from __future__ import annotations

import os
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func

from app.constants import IncidentStatus, Roles
from app.extensions import db
from app.models.admin_audit_log import AdminAuditLog
from app.models.admin_preference import AdminPreference
from app.models.authority import Authority
from app.models.incident import Incident
from app.models.incident_assignment import IncidentAssignment
from app.models.incident_category import IncidentCategory
from app.models.incident_dispatch import IncidentDispatch
from app.models.location import Location
from app.models.routing_rule import RoutingRule
from app.models.user import User
from app.services.analytics_service import AnalyticsService
from app.services.auth_service import auth_service
from app.services.dashboard_service import dashboard_service
from app.services.incident_service import incident_service
from app.utils.decorators import role_required
from app.utils.validators import (
    validate_admin_create_user_invite,
    validate_admin_update_user_form,
)

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")


def _get_or_create_admin_prefs(user_id: int) -> AdminPreference:
    prefs = db.session.query(AdminPreference).filter(AdminPreference.user_id == user_id).first()
    if prefs is not None:
        return prefs
    prefs = AdminPreference(user_id=user_id)
    db.session.add(prefs)
    db.session.commit()
    return prefs


def _parse_status_filter(raw: str | None) -> IncidentStatus | None:
    if not raw:
        return None
    try:
        return IncidentStatus(raw)
    except ValueError:
        return None


@admin_bp.route("/dashboard")
@login_required
@role_required(Roles.ADMIN)
def dashboard():
    prefs = _get_or_create_admin_prefs(getattr(current_user, "id", 0))
    overview = dashboard_service.get_overview()
    recent_incidents = dashboard_service.get_recent_incidents(limit=5)
    overdue_incidents = dashboard_service.get_overdue_incidents(limit=5)
    authority_overview = dashboard_service.get_overview_by_authority(limit=3)

    # Lightweight user stats for the optional dashboard panel.
    total_users = db.session.query(func.count(User.id)).scalar() or 0
    residents = (
        db.session.query(func.count(User.id)).filter(User.role == Roles.RESIDENT.value).scalar()
        or 0
    )
    authorities = (
        db.session.query(func.count(User.id)).filter(User.role == Roles.AUTHORITY.value).scalar()
        or 0
    )
    admins = (
        db.session.query(func.count(User.id)).filter(User.role == Roles.ADMIN.value).scalar() or 0
    )
    inactive = db.session.query(func.count(User.id)).filter(User.is_active.is_(False)).scalar() or 0

    user_stats = {
        "total": total_users,
        "residents": residents,
        "authorities": authorities,
        "admins": admins,
        "inactive": inactive,
    }

    return render_template(
        "admin/dashboard.html",
        prefs=prefs,
        overview=overview,
        recent_incidents=recent_incidents,
        overdue_incidents=overdue_incidents,
        authority_overview=authority_overview,
        user_stats=user_stats,
    )


@admin_bp.route("/controls", methods=["GET", "POST"])
@login_required
@role_required(Roles.ADMIN)
def controls():
    prefs = _get_or_create_admin_prefs(getattr(current_user, "id", 0))

    if request.method == "POST":
        form_data = request.form.to_dict()

        def _bool(name: str) -> bool:
            return form_data.get(name) in ("1", "on", "yes", "true", True)

        prefs.show_kpi_cards = _bool("show_kpi_cards")
        prefs.show_recent_incidents = _bool("show_recent_incidents")
        prefs.show_overdue_panel = _bool("show_overdue_panel")
        prefs.show_user_stats = _bool("show_user_stats")

        prefs.notify_new_incident = _bool("notify_new_incident")
        prefs.notify_overdue_incident = _bool("notify_overdue_incident")
        prefs.daily_summary_enabled = _bool("daily_summary_enabled")

        landing = (form_data.get("default_landing_page") or "dashboard").strip().lower()
        if landing not in ("dashboard", "incidents", "users", "authorities", "routing_rules"):
            landing = "dashboard"
        prefs.default_landing_page = landing

        sort = (form_data.get("default_incident_sort") or "newest").strip().lower()
        if sort not in ("newest", "oldest"):
            sort = "newest"
        prefs.default_incident_sort = sort

        rows_raw = (form_data.get("default_rows_per_page") or "").strip()
        prefs.default_rows_per_page = int(rows_raw) if rows_raw.isdigit() else 25

        db.session.add(
            AdminAuditLog(
                admin_user_id=getattr(current_user, "id", None),
                action="admin_preferences_updated",
                target_type="admin_preferences",
                target_id=prefs.id,
                details={
                    "default_landing_page": prefs.default_landing_page,
                    "default_incident_sort": prefs.default_incident_sort,
                    "default_rows_per_page": prefs.default_rows_per_page,
                },
            )
        )
        db.session.commit()
        flash("Admin controls updated.", "success")
        return redirect(url_for("admin.controls"))

    return render_template("admin/controls.html", prefs=prefs)


analytics_service = AnalyticsService()


@admin_bp.route("/analytics")
@login_required
@role_required(Roles.ADMIN)
def analytics():
    """Analytics dashboard: volume, resolution times, hotspots, authority performance."""
    summary = analytics_service.get_dashboard_summary(days=7)
    return render_template(
        "admin/analytics.html",
        summary=summary,
    )


@admin_bp.route("/incidents")
@login_required
@role_required(Roles.ADMIN)
def incidents():
    status_param = request.args.get("status") or ""
    q = request.args.get("q") or ""
    category = request.args.get("category") or ""
    severity = request.args.get("severity") or ""
    authority_id_raw = request.args.get("authority_id") or ""
    unassigned_only_raw = request.args.get("unassigned_only") or ""
    page_raw = request.args.get("page") or "1"
    area = request.args.get("area") or ""
    date_from_raw = request.args.get("date_from") or ""
    date_to_raw = request.args.get("date_to") or ""
    sort = (request.args.get("sort") or "newest").strip().lower()

    try:
        page = int(page_raw)
    except ValueError:
        page = 1

    status_filter = _parse_status_filter(status_param or None)

    authority_id: int | None = None
    if authority_id_raw:
        try:
            authority_id = int(authority_id_raw)
        except ValueError:
            authority_id = None

    unassigned_only = unassigned_only_raw in ("1", "true", "on", "yes")

    date_from = None
    date_to = None
    if date_from_raw:
        try:
            date_from = datetime.fromisoformat(date_from_raw)
        except ValueError:
            date_from = None
    if date_to_raw:
        try:
            dt = datetime.fromisoformat(date_to_raw)
            date_to = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        except ValueError:
            date_to = None
    incident_page = incident_service.incident_repo.list_for_admin(
        status=status_filter,
        q=q or None,
        category=category or None,
        severity=severity or None,
        authority_id=authority_id,
        unassigned_only=unassigned_only,
        date_from=date_from,
        date_to=date_to,
        area=area or None,
        sort=sort or "newest",
        page=page,
        per_page=25,
    )

    overview = dashboard_service.get_overview()
    google_maps_api_key = current_app.config.get("GOOGLE_MAPS_API_KEY")
    authorities = (
        db.session.query(Authority)
        .filter(Authority.is_active.is_(True))
        .order_by(Authority.name.asc())
        .all()
    )
    return render_template(
        "admin/incidents/index.html",
        overview=overview,
        page=incident_page,
        selected_status=status_param,
        q=q,
        selected_category=category,
        selected_severity=severity,
        authorities=authorities,
        selected_authority_id=authority_id_raw,
        unassigned_only=unassigned_only,
        area=area,
        date_from=date_from_raw,
        date_to=date_to_raw,
        sort=sort,
        google_maps_api_key=google_maps_api_key,
    )


@admin_bp.route("/incidents/<int:incident_id>")
@login_required
@role_required(Roles.ADMIN)
def incident_detail(incident_id: int):
    incident, updates = incident_service.get_incident_with_history(
        incident_id,
        current_user,  # type: ignore[arg-type]
    )
    if incident is None:
        flash("Incident not found.", "warning")
        return redirect(url_for("admin.incidents"))

    media = list(incident.media.all())
    timeline = incident_service.assemble_timeline(incident_id)
    return render_template(
        "admin/incidents/detail.html",
        incident=incident,
        updates=updates,
        timeline=timeline,
        media=media,
    )


@admin_bp.route("/incidents/<int:incident_id>/screening/confirm", methods=["POST"])
@login_required
@role_required(Roles.ADMIN)
def confirm_screening(incident_id: int):
    incident = incident_service.incident_repo.get_by_id(incident_id)
    if incident is None:
        flash("Incident not found.", "warning")
        return redirect(url_for("admin.incidents"))

    if not incident.suggested_authority_id:
        flash("No suggested department to confirm for this incident.", "warning")
        return redirect(url_for("admin.incident_detail", incident_id=incident_id))

    from app.models import Authority  # local import to avoid circulars

    authority = db.session.get(Authority, incident.suggested_authority_id)
    if authority is None or not authority.is_active:
        flash("Suggested department is no longer available.", "warning")
        return redirect(url_for("admin.incident_detail", incident_id=incident_id))

    incident.current_authority_id = authority.id
    incident.requires_admin_review = False

    assignment = IncidentAssignment(
        incident_id=incident.id,
        authority_id=authority.id,
        assigned_by_user_id=getattr(current_user, "id", None),
    )
    db.session.add(assignment)
    db.session.flush()
    dispatch = IncidentDispatch(
        incident_assignment_id=assignment.id,
        incident_id=incident.id,
        authority_id=authority.id,
        dispatch_method="internal_queue",
        dispatched_by_type="admin",
        dispatched_by_id=getattr(current_user, "id", None),
        delivery_status="pending",
        ack_status="pending",
    )
    db.session.add(dispatch)

    db.session.add(
        AdminAuditLog(
            admin_user_id=getattr(current_user, "id", None),
            action="screening_confirmed",
            target_type="incident",
            target_id=incident.id,
            details={"authority_id": authority.id},
        )
    )
    db.session.commit()
    flash("Screening suggestion confirmed. Incident assigned to department.", "success")
    return redirect(url_for("admin.incident_detail", incident_id=incident_id))


@admin_bp.route("/incidents/<int:incident_id>/status", methods=["POST"])
@login_required
@role_required(Roles.ADMIN)
def update_incident_status(incident_id: int):
    to_status_raw = request.form.get("status") or ""
    note = request.form.get("note") or ""

    try:
        to_status = IncidentStatus(to_status_raw)
    except ValueError:
        flash("Invalid status.", "danger")
        return redirect(url_for("admin.incident_detail", incident_id=incident_id))

    ok, errors = incident_service.update_status(
        incident_id=incident_id,
        to_status=to_status,
        note=note,
        authority_user=current_user,  # type: ignore[arg-type]
        allow_admin_override=True,
    )

    if not ok:
        for error in errors:
            flash(error, "danger")
    else:
        flash("Incident status updated.", "success")
        db.session.add(
            AdminAuditLog(
                admin_user_id=getattr(current_user, "id", None),
                action="incident_status_updated",
                target_type="incident",
                target_id=incident_id,
                details={"to_status": to_status.value, "note_present": bool(note.strip())},
            )
        )
        db.session.commit()

    return redirect(url_for("admin.incident_detail", incident_id=incident_id))


@admin_bp.route("/users")
@login_required
@role_required(Roles.ADMIN)
def users():
    role = request.args.get("role") or ""
    search = request.args.get("search") or ""
    page_raw = request.args.get("page") or "1"
    try:
        page = int(page_raw)
    except ValueError:
        page = 1

    user_page = auth_service.user_repo.list_users(
        role=role or None,
        search=search or None,
        page=page,
        per_page=25,
    )
    user_stats = auth_service.user_repo.get_stats()
    return render_template(
        "admin/users/index.html",
        page=user_page,
        selected_role=role,
        search=search,
        user_stats=user_stats,
    )


@admin_bp.route("/users/new", methods=["GET", "POST"])
@login_required
@role_required(Roles.ADMIN)
def user_new():
    if request.method == "POST":
        form_data = request.form.to_dict()
        errors = validate_admin_create_user_invite(form_data)
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("admin/users/new.html", form_data=form_data)

        user, invite_token, service_errors = auth_service.create_user_invite(
            name=form_data.get("name", ""),
            email=form_data.get("email", ""),
            role=form_data.get("role", Roles.RESIDENT.value),
        )
        if service_errors or user is None:
            for e in service_errors or ["Failed to create user."]:
                flash(e, "danger")
            return render_template("admin/users/new.html", form_data=form_data)

        flash(
            "User created. Share the set-password link with them; they choose their own password.",
            "success",
        )
        return redirect(url_for("admin.user_detail", user_id=user.id, invite_token=invite_token))

    return render_template("admin/users/new.html", form_data=None)


@admin_bp.route("/users/<int:user_id>")
@login_required
@role_required(Roles.ADMIN)
def user_detail(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "warning")
        return redirect(url_for("admin.users"))
    invite_url = None
    invite_token = request.args.get("invite_token")
    if invite_token:
        invite_url = url_for("auth.set_password", token=invite_token, _external=True)
    return render_template(
        "admin/users/detail.html",
        user=user,
        form_data=None,
        invite_url=invite_url,
    )


@admin_bp.route("/users/<int:user_id>", methods=["POST"])
@login_required
@role_required(Roles.ADMIN)
def user_update(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "warning")
        return redirect(url_for("admin.users"))

    form_data = request.form.to_dict()
    errors = validate_admin_update_user_form(form_data)

    email = (form_data.get("email") or "").strip().lower()
    if email and email != (user.email or "").lower():
        existing = auth_service.user_repo.get_by_email(email)
        if existing and existing.id != user.id:
            errors.append("An account with that email already exists.")

    if errors:
        for e in errors:
            flash(e, "danger")
        return render_template("admin/users/detail.html", user=user, form_data=form_data)

    # Prevent admins from accidentally locking themselves out.
    is_self = user.id == getattr(current_user, "id", None)

    user.name = (form_data.get("name") or "").strip()
    user.email = email
    user.role = (form_data.get("role") or user.role).strip()
    new_is_active = form_data.get("is_active") in ("1", "on", "yes", "true", True)
    if is_self and not new_is_active:
        flash("You cannot deactivate your own account while signed in as admin.", "danger")
        return render_template("admin/users/detail.html", user=user, form_data=form_data)
    user.is_active = new_is_active

    db.session.add(
        AdminAuditLog(
            admin_user_id=getattr(current_user, "id", None),
            action="user_updated",
            target_type="user",
            target_id=user.id,
            details={
                "role": user.role,
                "is_active": user.is_active,
            },
        )
    )
    db.session.commit()
    flash("User updated.", "success")
    return redirect(url_for("admin.user_detail", user_id=user.id))


@admin_bp.route("/users/<int:user_id>/send-password-reset", methods=["POST"])
@login_required
@role_required(Roles.ADMIN)
def send_user_password_reset(user_id: int):
    """Send a password reset email (tokenized set-password link)."""
    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "warning")
        return redirect(url_for("admin.users"))

    ok, errors = auth_service.send_password_reset_email(user)
    if not ok:
        for e in errors:
            flash(e, "danger")
        return redirect(url_for("admin.user_detail", user_id=user.id))

    db.session.add(
        AdminAuditLog(
            admin_user_id=getattr(current_user, "id", None),
            action="user_password_reset_requested",
            target_type="user",
            target_id=user.id,
            details={"email": user.email},
        )
    )
    db.session.commit()

    flash("Password reset email sent (or queued).", "success")
    return redirect(url_for("admin.user_detail", user_id=user.id))


@admin_bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@login_required
@role_required(Roles.ADMIN)
def reset_user_password(user_id: int):
    """Back-compat route: forwards to the email reset flow."""
    return send_user_password_reset(user_id)


@admin_bp.route("/users/<int:user_id>/send-email-verification", methods=["POST"])
@login_required
@role_required(Roles.ADMIN)
def send_user_email_verification(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "warning")
        return redirect(url_for("admin.users"))

    # MVP: verification flows are system-driven; admin can only trigger actions.
    # If/when verification tokens are implemented, wire them here.
    db.session.add(
        AdminAuditLog(
            admin_user_id=getattr(current_user, "id", None),
            action="user_email_verification_requested",
            target_type="user",
            target_id=user.id,
            details={"email": user.email},
        )
    )
    db.session.commit()
    flash("Verification email flow is not configured yet.", "warning")
    return redirect(url_for("admin.user_detail", user_id=user.id))


@admin_bp.route("/users/<int:user_id>/send-phone-otp", methods=["POST"])
@login_required
@role_required(Roles.ADMIN)
def send_user_phone_otp(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "warning")
        return redirect(url_for("admin.users"))

    db.session.add(
        AdminAuditLog(
            admin_user_id=getattr(current_user, "id", None),
            action="user_phone_otp_requested",
            target_type="user",
            target_id=user.id,
            details={"email": user.email},
        )
    )
    db.session.commit()
    flash("Phone OTP flow is not configured yet.", "warning")
    return redirect(url_for("admin.user_detail", user_id=user.id))


@admin_bp.route("/authorities")
@login_required
@role_required(Roles.ADMIN)
def authorities():
    authorities = db.session.query(Authority).order_by(Authority.name.asc()).all()
    return render_template("admin/authorities/index.html", authorities=authorities)


@admin_bp.route("/authorities/<int:authority_id>", methods=["GET", "POST"])
@login_required
@role_required(Roles.ADMIN)
def authority_detail(authority_id: int):
    authority = db.session.get(Authority, authority_id)
    if authority is None:
        flash("Department not found.", "warning")
        return redirect(url_for("admin.authorities"))

    if request.method == "POST":
        form_data = request.form.to_dict()
        authority.name = (form_data.get("name") or "").strip() or authority.name
        authority.authority_type = (form_data.get("authority_type") or "").strip() or None
        authority.contact_email = (form_data.get("contact_email") or "").strip() or None
        authority.contact_phone = (form_data.get("contact_phone") or "").strip() or None
        authority.jurisdiction_notes = (form_data.get("jurisdiction_notes") or "").strip() or None
        authority.is_active = form_data.get("is_active") in ("1", "on", "yes", "true", True)

        db.session.add(
            AdminAuditLog(
                admin_user_id=getattr(current_user, "id", None),
                action="authority_updated",
                target_type="authority",
                target_id=authority.id,
                details={"name": authority.name, "is_active": authority.is_active},
            )
        )
        db.session.commit()
        flash("Department updated.", "success")
        return redirect(url_for("admin.authority_detail", authority_id=authority.id))

    member_count = authority.members.count()
    open_statuses = [
        IncidentStatus.REPORTED.value,
        IncidentStatus.SCREENED.value,
        IncidentStatus.ASSIGNED.value,
        IncidentStatus.IN_PROGRESS.value,
    ]
    open_incidents = (
        db.session.query(func.count(Incident.id))
        .filter(
            Incident.current_authority_id == authority.id,
            Incident.status.in_(open_statuses),
        )
        .scalar()
        or 0
    )
    total_assigned = (
        db.session.query(func.count(Incident.id))
        .filter(Incident.current_authority_id == authority.id)
        .scalar()
        or 0
    )

    routing_rule_count = (
        db.session.query(func.count(RoutingRule.id))
        .filter(RoutingRule.authority_id == authority.id)
        .scalar()
        or 0
    )

    routing_rules = (
        db.session.query(RoutingRule)
        .filter(RoutingRule.authority_id == authority.id)
        .order_by(RoutingRule.is_active.desc(), RoutingRule.id.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "admin/authorities/detail.html",
        authority=authority,
        routing_rule_count=routing_rule_count,
        routing_rules=routing_rules,
        member_count=member_count,
        open_incidents=open_incidents,
        total_assigned=total_assigned,
        form_data=request.form if request.method == "POST" else None,
    )


@admin_bp.route("/authorities/new", methods=["GET", "POST"])
@login_required
@role_required(Roles.ADMIN)
def authority_new():
    if request.method == "POST":
        form_data = request.form.to_dict()
        name = (form_data.get("name") or "").strip()
        if not name:
            flash("Name is required.", "danger")
            return render_template(
                "admin/authorities/detail.html",
                authority=Authority(name=""),
                routing_rule_count=0,
                form_data=form_data,
            )

        authority = Authority(
            name=name,
            authority_type=(form_data.get("authority_type") or "").strip() or None,
            contact_email=(form_data.get("contact_email") or "").strip() or None,
            contact_phone=(form_data.get("contact_phone") or "").strip() or None,
            jurisdiction_notes=(form_data.get("jurisdiction_notes") or "").strip() or None,
            is_active=form_data.get("is_active") in ("1", "on", "yes", "true", True),
        )
        db.session.add(authority)
        db.session.flush()
        db.session.add(
            AdminAuditLog(
                admin_user_id=getattr(current_user, "id", None),
                action="authority_created",
                target_type="authority",
                target_id=authority.id,
                details={"name": authority.name},
            )
        )
        db.session.commit()
        flash("Department created.", "success")
        return redirect(url_for("admin.authorities"))

    tmp_authority = Authority(name="")
    return render_template(
        "admin/authorities/detail.html",
        authority=tmp_authority,
        routing_rule_count=0,
        form_data=request.form if request.method == "POST" else None,
    )


@admin_bp.route("/routing-rules")
@login_required
@role_required(Roles.ADMIN)
def routing_rules():
    rules = (
        db.session.query(RoutingRule)
        .join(RoutingRule.category)
        .join(RoutingRule.authority)
        .order_by(RoutingRule.id.desc())
        .all()
    )
    return render_template("admin/routing_rules/index.html", rules=rules)


@admin_bp.route("/routing-rules/new", methods=["GET", "POST"])
@login_required
@role_required(Roles.ADMIN)
def routing_rule_new():
    categories = db.session.query(IncidentCategory).order_by(IncidentCategory.name.asc()).all()
    locations = db.session.query(Location).order_by(Location.area_name.asc()).all()
    authorities = db.session.query(Authority).order_by(Authority.name.asc()).all()

    if request.method == "POST":
        form_data = request.form.to_dict()
        try:
            category_id = int(form_data.get("category_id") or "0")
            authority_id = int(form_data.get("authority_id") or "0")
        except ValueError:
            category_id = 0
            authority_id = 0

        if not category_id or not authority_id:
            flash("Category and department are required.", "danger")
            return render_template(
                "admin/routing_rules/detail.html",
                rule=RoutingRule(is_active=True),
                categories=categories,
                locations=locations,
                authorities=authorities,
                form_data=form_data,
            )

        location_id_raw = form_data.get("location_id") or ""
        location_id = int(location_id_raw) if location_id_raw.isdigit() else None

        rule = RoutingRule(
            category_id=category_id,
            location_id=location_id,
            authority_id=authority_id,
            priority_override=(form_data.get("priority_override") or "").strip() or None,
            sla_hours_override=(
                int(form_data.get("sla_hours_override"))
                if (form_data.get("sla_hours_override") or "").strip().isdigit()
                else None
            ),
            is_active=form_data.get("is_active") in ("1", "on", "yes", "true", True),
        )
        db.session.add(rule)
        db.session.flush()
        db.session.add(
            AdminAuditLog(
                admin_user_id=getattr(current_user, "id", None),
                action="routing_rule_created",
                target_type="routing_rule",
                target_id=rule.id,
                details={"category_id": rule.category_id, "authority_id": rule.authority_id},
            )
        )
        db.session.commit()
        flash("Routing rule created.", "success")
        return redirect(url_for("admin.routing_rule_detail", rule_id=rule.id))

    return render_template(
        "admin/routing_rules/detail.html",
        rule=RoutingRule(is_active=True),
        categories=categories,
        locations=locations,
        authorities=authorities,
        form_data=request.form if request.method == "POST" else {},
    )


@admin_bp.route("/routing-rules/<int:rule_id>", methods=["GET", "POST"])
@login_required
@role_required(Roles.ADMIN)
def routing_rule_detail(rule_id: int):
    rule = db.session.get(RoutingRule, rule_id)
    if rule is None:
        flash("Routing rule not found.", "warning")
        return redirect(url_for("admin.routing_rules"))

    categories = db.session.query(IncidentCategory).order_by(IncidentCategory.name.asc()).all()
    locations = db.session.query(Location).order_by(Location.area_name.asc()).all()
    authorities = db.session.query(Authority).order_by(Authority.name.asc()).all()

    if request.method == "POST":
        form_data = request.form.to_dict()
        try:
            rule.category_id = int(form_data.get("category_id") or rule.category_id)
            rule.authority_id = int(form_data.get("authority_id") or rule.authority_id)
        except ValueError:
            flash("Category and department are required.", "danger")
            return render_template(
                "admin/routing_rules/detail.html",
                rule=rule,
                categories=categories,
                locations=locations,
                authorities=authorities,
                form_data=form_data,
            )

        location_id_raw = form_data.get("location_id") or ""
        rule.location_id = int(location_id_raw) if location_id_raw.isdigit() else None
        rule.priority_override = (form_data.get("priority_override") or "").strip() or None
        rule.sla_hours_override = (
            int(form_data.get("sla_hours_override"))
            if (form_data.get("sla_hours_override") or "").strip().isdigit()
            else None
        )
        rule.is_active = form_data.get("is_active") in ("1", "on", "yes", "true", True)

        db.session.add(
            AdminAuditLog(
                admin_user_id=getattr(current_user, "id", None),
                action="routing_rule_updated",
                target_type="routing_rule",
                target_id=rule.id,
                details={"category_id": rule.category_id, "authority_id": rule.authority_id},
            )
        )
        db.session.commit()
        flash("Routing rule updated.", "success")
        return redirect(url_for("admin.routing_rule_detail", rule_id=rule.id))

    return render_template(
        "admin/routing_rules/detail.html",
        rule=rule,
        categories=categories,
        locations=locations,
        authorities=authorities,
        form_data=request.form
        if request.method == "POST"
        else {
            "category_id": rule.category_id,
            "location_id": rule.location_id or "",
            "authority_id": rule.authority_id,
            "priority_override": rule.priority_override or "",
            "sla_hours_override": rule.sla_hours_override or "",
            "is_active": "on" if rule.is_active else "",
        },
    )


@admin_bp.route("/incidents/<int:incident_id>/media/<path:filename>")
@login_required
@role_required(Roles.ADMIN)
def serve_incident_media_admin(incident_id: int, filename: str):
    """Serve incident evidence to admins."""
    incident = incident_service.incident_repo.get_by_id(incident_id)
    if incident is None:
        return "", 404

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    incident_dir = os.path.join(upload_folder, "incidents", str(incident_id))
    if not os.path.abspath(incident_dir).startswith(os.path.abspath(upload_folder)):
        return "", 404

    return send_from_directory(incident_dir, filename)
