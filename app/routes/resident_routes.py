from __future__ import annotations

import os

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
from werkzeug.datastructures import FileStorage

from app.constants import IncidentStatus, Roles
from app.extensions import db, limiter
from app.models import IncidentCategory
from app.services.incident_presets import get_preset
from app.services.incident_service import incident_service
from app.services.resident_profile_service import (
    get_or_create_profile,
    is_profile_complete,
    update_profile,
)
from app.utils.decorators import role_required

resident_bp = Blueprint("resident", __name__, template_folder="../templates/resident")


def _build_preset_for_template(preset: dict) -> dict:
    """Flatten preset for Jinja: suggested_title, urgency_value, helper_prompts, safety_tip, ask_*."""
    default_urgency = preset.get("default_urgency")
    urgency_value = (
        getattr(default_urgency, "value", default_urgency)
        if default_urgency is not None
        else "soon"
    )
    return {
        "suggested_title": preset.get("suggested_title") or "Incident reported",
        "urgency_value": urgency_value,
        "helper_prompts": preset.get("helper_prompts") or [],
        "safety_tip": preset.get("safety_tip") or "",
        "ask_is_happening_now": preset.get("ask_is_happening_now", False),
        "ask_is_anyone_in_danger": preset.get("ask_is_anyone_in_danger", False),
        "ask_is_issue_still_present": preset.get("ask_is_issue_still_present", False),
    }


def _resident_rate_key() -> str:
    from flask import request

    if current_user.is_authenticated:
        return f"resident:{current_user.id}"
    return request.remote_addr or "anon"


@resident_bp.route("/profile", methods=["GET", "POST"])
@login_required
@role_required(Roles.RESIDENT)
def profile():
    profile_obj = get_or_create_profile(current_user)  # type: ignore[arg-type]
    if request.method == "POST":
        profile_obj, errors = update_profile(
            current_user,  # type: ignore[arg-type]
            request.form.to_dict(),
        )
        if errors:
            for e in errors:
                flash(e, "danger")
            # Re-render with submitted form data so resident doesn't lose edits
            return render_template(
                "resident/profile.html",
                profile=profile_obj,
                form_data=request.form,
                next_url=request.args.get("next") or request.form.get("next"),
            )
        flash("Profile saved.", "success")
        next_url = request.args.get("next") or request.form.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for("resident.profile"))
    return render_template(
        "resident/profile.html",
        profile=profile_obj,
        form_data=None,
        next_url=request.args.get("next"),
    )


@resident_bp.route("/dashboard")
@login_required
@role_required(Roles.RESIDENT)
def dashboard():
    incidents = list(
        incident_service.list_incidents_for_resident(current_user)  # type: ignore[arg-type]
    )
    counts = {
        "total": len(incidents),
        "pending": sum(1 for i in incidents if i.status == IncidentStatus.PENDING.value),
        "in_progress": sum(1 for i in incidents if i.status == IncidentStatus.IN_PROGRESS.value),
        "resolved": sum(1 for i in incidents if i.status == IncidentStatus.RESOLVED.value),
        "rejected": sum(1 for i in incidents if i.status == IncidentStatus.REJECTED.value),
    }
    total_incidents = counts["total"]
    pending_count = counts["pending"]
    in_progress_count = counts["in_progress"]
    # Resolved / Closed includes resolved and rejected
    resolved_count = counts["resolved"] + counts["rejected"]
    active_cases = pending_count + in_progress_count
    recent_incidents = incidents[:6]
    profile_complete = is_profile_complete(current_user)  # type: ignore[arg-type]
    return render_template(
        "resident/dashboard.html",
        total_incidents=total_incidents,
        pending_count=pending_count,
        in_progress_count=in_progress_count,
        resolved_count=resolved_count,
        active_cases=active_cases,
        recent_incidents=recent_incidents,
        profile_complete=profile_complete,
    )


@resident_bp.route("/incidents/new", methods=["GET", "POST"])
@login_required
@role_required(Roles.RESIDENT)
@limiter.limit("3 per minute", key_func=_resident_rate_key)
def report_incident():
    if not is_profile_complete(current_user):  # type: ignore[arg-type]
        flash("Complete your profile to report an incident.", "warning")
        return redirect(url_for("resident.profile", next=url_for("resident.report_incident")))
    if request.method == "POST":
        payload = request.form.to_dict()
        files = request.files.getlist("evidence")
        files = [f for f in files if f and isinstance(f, FileStorage) and f.filename]
        incident, errors = incident_service.create_incident(
            payload,
            current_user,  # type: ignore[arg-type]
            files=files or None,
        )

        if errors:
            for error in errors:
                flash(error, "danger")
            similar = []
            category_name = payload.get("category", "")
            suburb = payload.get("suburb_or_ward", "")
            if payload.get("category_id"):
                try:
                    cat_obj = db.session.get(IncidentCategory, int(payload["category_id"]))
                    if cat_obj is not None:
                        category_name = cat_obj.name
                except (TypeError, ValueError):
                    pass
            if category_name or suburb:
                similar = incident_service.suggest_similar_for_resident(
                    category_name,
                    suburb,
                )
            categories = (
                db.session.query(IncidentCategory)
                .filter(IncidentCategory.is_active.is_(True))
                .order_by(IncidentCategory.name)
                .all()
            )
            profile_obj = get_or_create_profile(current_user)  # type: ignore[arg-type]
            saved_address = {
                "suburb": getattr(profile_obj, "suburb", None) or "",
                "street": getattr(profile_obj, "street_address_1", None) or "",
            }
            presets = {c.id: _build_preset_for_template(get_preset(c)) for c in categories}
            other_preset = _build_preset_for_template(get_preset("other"))
            return render_template(
                "resident/report_incident.html",
                form_data=payload,
                similar_incidents=similar,
                categories=categories,
                saved_address=saved_address,
                presets=presets,
                other_preset=other_preset,
            )

        flash("Incident reported successfully.", "success")
        return redirect(url_for("resident.my_incidents"))

    similar = []
    if request.args.get("category") and request.args.get("suburb_or_ward"):
        similar = incident_service.suggest_similar_for_resident(
            request.args.get("category", ""),
            request.args.get("suburb_or_ward", ""),
        )
    categories = (
        db.session.query(IncidentCategory)
        .filter(IncidentCategory.is_active.is_(True))
        .order_by(IncidentCategory.name)
        .all()
    )
    profile_obj = get_or_create_profile(current_user)  # type: ignore[arg-type]
    saved_address = {
        "suburb": getattr(profile_obj, "suburb", None) or "",
        "street": getattr(profile_obj, "street_address_1", None) or "",
    }
    presets = {c.id: _build_preset_for_template(get_preset(c)) for c in categories}
    other_preset = _build_preset_for_template(get_preset("other"))
    return render_template(
        "resident/report_incident.html",
        similar_incidents=similar,
        categories=categories,
        saved_address=saved_address,
        presets=presets,
        other_preset=other_preset,
    )


@resident_bp.route("/incidents")
@login_required
@role_required(Roles.RESIDENT)
def my_incidents():
    status_param = request.args.get("status")
    status_filter = None
    if status_param:
        try:
            status_filter = IncidentStatus(status_param)
        except ValueError:
            pass
    incidents = incident_service.list_incidents_for_resident(
        current_user,  # type: ignore[arg-type]
        status=status_filter,
    )
    return render_template(
        "resident/my_incidents.html",
        incidents=incidents,
        selected_status=status_param or "",
    )


@resident_bp.route("/incidents/<int:incident_id>")
@login_required
@role_required(Roles.RESIDENT)
def incident_detail(incident_id: int):
    incident, updates = incident_service.get_incident_with_history(
        incident_id,
        current_user,  # type: ignore[arg-type]
    )
    if incident is None:
        flash("Incident not found.", "warning")
        return redirect(url_for("resident.my_incidents"))

    if incident.reported_by_id != current_user.id:
        flash("You do not have access to that incident.", "danger")
        return redirect(url_for("resident.my_incidents"))

    media = list(incident.media.all())
    can_edit = incident_service.can_resident_edit(
        incident,
        current_user,  # type: ignore[arg-type]
    )
    return render_template(
        "resident/incident_detail.html",
        incident=incident,
        updates=updates,
        media=media,
        can_edit=can_edit,
    )


@resident_bp.route("/incidents/<int:incident_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(Roles.RESIDENT)
def edit_incident(incident_id: int):
    incident, updates = incident_service.get_incident_with_history(
        incident_id,
        current_user,  # type: ignore[arg-type]
    )
    if incident is None:
        flash("Incident not found.", "warning")
        return redirect(url_for("resident.my_incidents"))
    if incident.reported_by_id != current_user.id:
        flash("You do not have access to that incident.", "danger")
        return redirect(url_for("resident.my_incidents"))
    if not incident_service.can_resident_edit(
        incident,
        current_user,  # type: ignore[arg-type]
    ):
        flash("This incident can no longer be edited.", "warning")
        return redirect(url_for("resident.incident_detail", incident_id=incident_id))

    if request.method == "POST":
        payload = request.form.to_dict()
        _, errors = incident_service.update_incident_by_resident(
            incident_id,
            current_user,  # type: ignore[arg-type]
            payload,
        )
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "resident/edit_incident.html",
                incident=incident,
                form_data=payload,
            )
        flash("Incident updated.", "success")
        return redirect(url_for("resident.incident_detail", incident_id=incident_id))

    return render_template("resident/edit_incident.html", incident=incident)


@resident_bp.route("/incidents/<int:incident_id>/media", methods=["POST"])
@login_required
@role_required(Roles.RESIDENT)
def add_incident_media(incident_id: int):
    incident = incident_service.incident_repo.get_by_id(incident_id)
    if incident is None:
        flash("Incident not found.", "warning")
        return redirect(url_for("resident.my_incidents"))
    if incident.reported_by_id != current_user.id:
        flash("You do not have access to that incident.", "danger")
        return redirect(url_for("resident.my_incidents"))
    files = request.files.getlist("evidence")
    files = [f for f in files if f and isinstance(f, FileStorage) and f.filename]
    ok, errors = incident_service.attach_media(
        incident_id,
        current_user,  # type: ignore[arg-type]
        files,
    )
    if not ok and errors:
        for e in errors:
            flash(e, "danger")
    elif ok:
        flash("Evidence added.", "success")
    return redirect(url_for("resident.incident_detail", incident_id=incident_id))


@resident_bp.route("/incidents/<int:incident_id>/media/<path:filename>")
@login_required
@role_required(Roles.RESIDENT)
def serve_incident_media(incident_id: int, filename: str):
    """Serve an evidence image; resident must own the incident."""
    incident = incident_service.incident_repo.get_by_id(incident_id)
    if incident is None or incident.reported_by_id != current_user.id:
        return "", 404
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    incident_dir = os.path.join(upload_folder, "incidents", str(incident_id))
    if not os.path.abspath(incident_dir).startswith(os.path.abspath(upload_folder)):
        return "", 404
    return send_from_directory(incident_dir, filename)
