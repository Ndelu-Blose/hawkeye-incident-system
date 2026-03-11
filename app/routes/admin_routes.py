from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.constants import IncidentStatus, Roles
from app.extensions import db
from app.models.admin_audit_log import AdminAuditLog
from app.models.authority import Authority
from app.models.incident_category import IncidentCategory
from app.models.location import Location
from app.models.routing_rule import RoutingRule
from app.models.user import User
from app.services.auth_service import auth_service
from app.services.dashboard_service import dashboard_service
from app.services.incident_service import incident_service
from app.utils.decorators import role_required
from app.utils.security import hash_password
from app.utils.validators import (
    validate_admin_create_user_form,
    validate_admin_update_user_form,
)

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")


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
        overview=overview,
        recent_incidents=recent_incidents,
        overdue_incidents=overdue_incidents,
        authority_overview=authority_overview,
        user_stats=user_stats,
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
    incident_page = incident_service.incident_repo.list_for_admin(
        status=status_filter,
        q=q or None,
        category=category or None,
        severity=severity or None,
        authority_id=authority_id,
        unassigned_only=unassigned_only,
        page=page,
        per_page=25,
    )

    overview = dashboard_service.get_overview()
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
    return render_template(
        "admin/incidents/detail.html",
        incident=incident,
        updates=updates,
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
        errors = validate_admin_create_user_form(form_data)
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("admin/users/new.html", form_data=form_data)

        user, service_errors = auth_service.register_user(
            name=form_data.get("name", ""),
            email=form_data.get("email", ""),
            password=form_data.get("password", ""),
            role=form_data.get("role", Roles.RESIDENT.value),
        )
        if service_errors:
            for e in service_errors:
                flash(e, "danger")
            return render_template("admin/users/new.html", form_data=form_data)

        flash("User created.", "success")
        return redirect(url_for("admin.user_detail", user_id=user.id))

    return render_template("admin/users/new.html", form_data=None)


@admin_bp.route("/users/<int:user_id>")
@login_required
@role_required(Roles.ADMIN)
def user_detail(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "warning")
        return redirect(url_for("admin.users"))
    return render_template("admin/users/detail.html", user=user, form_data=None)


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
    user.email_verified = form_data.get("email_verified") in ("1", "on", "yes", "true", True)
    user.phone_verified = form_data.get("phone_verified") in ("1", "on", "yes", "true", True)

    db.session.commit()
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


@admin_bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@login_required
@role_required(Roles.ADMIN)
def reset_user_password(user_id: int):
    """Generate a temporary password for the user.

    In a real deployment this would send an email with a reset link.
    For this MVP we generate a strong temporary password and hash it.
    """
    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "warning")
        return redirect(url_for("admin.users"))

    import secrets
    import string

    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    temp_password = "".join(secrets.choice(alphabet) for _ in range(16))
    user.password_hash = hash_password(temp_password)
    db.session.commit()

    db.session.add(
        AdminAuditLog(
            admin_user_id=getattr(current_user, "id", None),
            action="user_password_reset",
            target_type="user",
            target_id=user.id,
            details=None,
        )
    )
    db.session.commit()

    if current_app.config.get("ENV") == "production":
        flash(
            "Temporary password generated. Ask the user to check their email or contact support.",
            "warning",
        )
    else:
        # In non-production environments, surface the temporary password to help with demos.
        flash(f"Temporary password for {user.email}: {temp_password}", "warning")

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

    routing_rule_count = (
        db.session.query(func.count(RoutingRule.id))
        .filter(RoutingRule.authority_id == authority.id)
        .scalar()
        or 0
    )
    return render_template(
        "admin/authorities/detail.html",
        authority=authority,
        routing_rule_count=routing_rule_count,
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
        return redirect(url_for("admin.authority_detail", authority_id=authority.id))

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
    locations = db.session.query(Location).order_by(Location.name.asc()).all()
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
    locations = db.session.query(Location).order_by(Location.name.asc()).all()
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
