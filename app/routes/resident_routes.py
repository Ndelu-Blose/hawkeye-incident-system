from __future__ import annotations

import os
import secrets
import uuid
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, or_
from werkzeug.datastructures import FileStorage

from app.constants import IncidentStatus, Roles
from app.extensions import db, limiter
from app.models import Incident, IncidentCategory
from app.services.analytics_service import AnalyticsService
from app.services.incident_dynamic_schema import (
    get_category_schema,
    serialize_schema,
)
from app.services.incident_presets import get_preset
from app.services.incident_service import incident_service
from app.services.resident_notification_service import resident_notification_service
from app.services.resident_profile_service import (
    get_or_create_profile,
    is_profile_complete,
    profile_completion_snapshot,
    update_profile,
)
from app.utils.decorators import role_required
from app.utils.uploads import allowed_image

resident_bp = Blueprint("resident", __name__, template_folder="../templates/resident")
analytics_service = AnalyticsService()


@resident_bp.app_context_processor
def inject_resident_notifications() -> dict:
    """Expose unread notification count for resident sidebar badge."""
    try:
        if current_user.is_authenticated and getattr(current_user, "role", None) == Roles.RESIDENT:
            return {
                "resident_unread_notifications": resident_notification_service.unread_count(
                    current_user
                )
            }  # type: ignore[arg-type]
    except Exception:
        # Never fail template render due to notification count.
        return {"resident_unread_notifications": 0}
    return {"resident_unread_notifications": 0}


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


def _extract_dynamic_details(form_data) -> dict:
    details: dict[str, object] = {}
    grouped: defaultdict[str, list[str]] = defaultdict(list)
    for key in form_data.keys():
        if not key.startswith("details__"):
            continue
        raw_name = key.removeprefix("details__")
        if raw_name.endswith("[]"):
            base = raw_name[:-2]
            grouped[base].extend([v for v in form_data.getlist(key) if v != ""])
            continue
        value = form_data.get(key, "")
        if value == "":
            continue
        details[raw_name] = value
    for key, values in grouped.items():
        if values:
            details[key] = values
    return details


def _resident_rate_key() -> str:
    from flask import request

    if current_user.is_authenticated:
        return f"resident:{current_user.id}"
    return request.remote_addr or "anon"


def _profile_avatar_dir(user_id: int) -> Path:
    return Path(current_app.config["UPLOAD_FOLDER"]) / "profiles" / str(user_id)


def _delete_profile_avatar(user_id: int, filename: str | None) -> None:
    if not filename:
        return
    avatar_path = _profile_avatar_dir(user_id) / filename
    try:
        avatar_path.unlink(missing_ok=True)
    except OSError:
        return


def _save_resized_profile_avatar(
    file_storage: FileStorage, user_id: int
) -> tuple[str | None, str | None]:
    try:
        file_storage.stream.seek(0)
        image = Image.open(file_storage.stream)
        image = ImageOps.exif_transpose(image)
    except (UnidentifiedImageError, OSError, ValueError):
        return None, "Invalid profile image. Please upload a valid JPG, PNG, or WebP file."

    # Store compact square thumbnails for faster loads in profile surfaces.
    image = image.convert("RGB")
    image.thumbnail((320, 320))

    safe_name = f"{uuid.uuid4().hex}_{secrets.token_hex(4)}.webp"
    avatar_dir = _profile_avatar_dir(user_id)
    avatar_dir.mkdir(parents=True, exist_ok=True)
    destination = avatar_dir / safe_name
    try:
        image.save(destination, format="WEBP", quality=82, method=6)
    except OSError:
        return None, "Could not process profile image. Please try another file."

    return safe_name, None


@resident_bp.route("/profile", methods=["GET", "POST"])
@login_required
@role_required(Roles.RESIDENT)
def profile():
    profile_obj = get_or_create_profile(current_user)  # type: ignore[arg-type]
    if request.method == "POST":
        payload = request.form.to_dict()
        old_avatar = profile_obj.avatar_filename
        remove_avatar = payload.get("remove_avatar") in {"1", "true", "on", "yes"}
        avatar_file = request.files.get("profile_image")
        if avatar_file and avatar_file.filename:
            if allowed_image(avatar_file.filename):
                saved_name, image_error = _save_resized_profile_avatar(avatar_file, current_user.id)
                if image_error:
                    flash(image_error, "warning")
                elif saved_name:
                    payload["avatar_filename"] = saved_name
            else:
                flash("Profile image type not allowed. Use JPG, PNG, or WebP.", "warning")
        elif remove_avatar:
            payload["avatar_filename"] = None

        profile_obj, errors = update_profile(
            current_user,  # type: ignore[arg-type]
            payload,
        )
        new_avatar = profile_obj.avatar_filename
        if remove_avatar and old_avatar and old_avatar != new_avatar:
            _delete_profile_avatar(current_user.id, old_avatar)
        elif avatar_file and avatar_file.filename and old_avatar and old_avatar != new_avatar:
            _delete_profile_avatar(current_user.id, old_avatar)
        if errors:
            for e in errors:
                flash(e, "danger")
            # Re-render with submitted form data so resident doesn't lose edits
            incidents = list(
                incident_service.list_incidents_for_resident(current_user)  # type: ignore[arg-type]
            )
            return render_template(
                "resident/profile.html",
                profile=profile_obj,
                form_data=request.form,
                next_url=request.args.get("next") or request.form.get("next"),
                profile_completion=profile_completion_snapshot(profile_obj),
                activity_counts={
                    "submitted": len(incidents),
                    "in_progress": sum(
                        1 for i in incidents if i.status == IncidentStatus.IN_PROGRESS.value
                    ),
                    "resolved": sum(
                        1
                        for i in incidents
                        if i.status in {IncidentStatus.RESOLVED.value, IncidentStatus.CLOSED.value}
                    ),
                },
                recent_activity=[
                    {
                        "label": f"Reported {i.title}",
                        "date_label": i.created_at.strftime("%d %b %Y")
                        if i.created_at
                        else "Recently",
                    }
                    for i in incidents[:5]
                ],
                google_maps_api_key=current_app.config.get("GOOGLE_MAPS_API_KEY"),
            )
        flash("Profile saved.", "success")
        next_url = request.args.get("next") or request.form.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for("resident.profile"))
    incidents = list(
        incident_service.list_incidents_for_resident(current_user)  # type: ignore[arg-type]
    )
    recent_activity = [
        {
            "label": f"Reported {i.title}",
            "date_label": i.created_at.strftime("%d %b %Y") if i.created_at else "Recently",
        }
        for i in incidents[:5]
    ]
    return render_template(
        "resident/profile.html",
        profile=profile_obj,
        form_data=None,
        next_url=request.args.get("next"),
        profile_completion=profile_completion_snapshot(profile_obj),
        activity_counts={
            "submitted": len(incidents),
            "in_progress": sum(
                1 for i in incidents if i.status == IncidentStatus.IN_PROGRESS.value
            ),
            "resolved": sum(
                1
                for i in incidents
                if i.status in {IncidentStatus.RESOLVED.value, IncidentStatus.CLOSED.value}
            ),
        },
        recent_activity=recent_activity,
        google_maps_api_key=current_app.config.get("GOOGLE_MAPS_API_KEY"),
    )


@resident_bp.route("/profile/avatar/<path:filename>")
@login_required
@role_required(Roles.RESIDENT)
def serve_profile_avatar(filename: str):
    profile_obj = get_or_create_profile(current_user)  # type: ignore[arg-type]
    if profile_obj.avatar_filename != filename:
        return "", 404
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    avatar_dir = os.path.join(upload_folder, "profiles", str(current_user.id))
    if not os.path.abspath(avatar_dir).startswith(os.path.abspath(upload_folder)):
        return "", 404
    return send_from_directory(avatar_dir, filename)


@resident_bp.route("/dashboard")
@login_required
@role_required(Roles.RESIDENT)
def dashboard():
    incidents = list(
        incident_service.list_incidents_for_resident(current_user)  # type: ignore[arg-type]
    )
    counts = {
        "total": len(incidents),
        "reported": sum(1 for i in incidents if i.status == IncidentStatus.REPORTED.value),
        "in_progress": sum(1 for i in incidents if i.status == IncidentStatus.IN_PROGRESS.value),
        "resolved": sum(1 for i in incidents if i.status == IncidentStatus.RESOLVED.value),
        "rejected": sum(1 for i in incidents if i.status == IncidentStatus.REJECTED.value),
    }
    total_incidents = counts["total"]
    pending_count = counts["reported"]
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
        google_maps_api_key=current_app.config.get("GOOGLE_MAPS_API_KEY"),
    )


@resident_bp.route("/api/resident/community-heatmap")
@login_required
@role_required(Roles.RESIDENT)
def community_heatmap():
    days_raw = request.args.get("days") or "7"
    category = (request.args.get("category") or "").strip() or None
    near_suburb = (request.args.get("near_suburb") or "").strip() or None
    try:
        days = max(1, min(int(days_raw), 90))
    except ValueError:
        days = 7
    payload = analytics_service.get_resident_community_heatmap(
        days=days,
        category=category,
        near_suburb=near_suburb,
    )
    return jsonify(payload)


@resident_bp.route("/notifications", methods=["GET"])
@login_required
@role_required(Roles.RESIDENT)
def notifications():
    # Visiting the list counts as having seen current notifications — advance cutoff
    # so per-item "New" badges and the sidebar count clear without an extra click.
    resident_notification_service.mark_all_read(current_user)  # type: ignore[arg-type]
    items = resident_notification_service.list_items(current_user, limit=60)  # type: ignore[arg-type]
    unread = resident_notification_service.unread_count(current_user)  # type: ignore[arg-type]
    return render_template(
        "resident/notifications.html",
        items=items,
        unread_count=unread,
    )


@resident_bp.route("/notifications/mark_read", methods=["POST"])
@login_required
@role_required(Roles.RESIDENT)
def notifications_mark_read():
    resident_notification_service.mark_all_read(current_user)  # type: ignore[arg-type]
    flash("All notifications marked as read.", "success")
    return redirect(url_for("resident.notifications"))


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
        payload["dynamic_details"] = _extract_dynamic_details(request.form)
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
            category_presets = {c.id: _build_preset_for_template(get_preset(c)) for c in categories}
            category_schemas = {
                c.id: serialize_schema(get_category_schema(c.name)) for c in categories
            }
            category_schemas_by_key = {
                c.name.strip().lower().replace(" ", "_"): serialize_schema(
                    get_category_schema(c.name)
                )
                for c in categories
            }
            other_preset = _build_preset_for_template(get_preset("other"))
            google_maps_api_key = current_app.config.get("GOOGLE_MAPS_API_KEY")
            return render_template(
                "resident/report_incident.html",
                form_data=payload,
                similar_incidents=similar,
                categories=categories,
                saved_address=saved_address,
                category_presets=category_presets,
                category_schemas=category_schemas,
                category_schemas_by_key=category_schemas_by_key,
                other_preset=other_preset,
                google_maps_api_key=google_maps_api_key,
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
    category_presets = {c.id: _build_preset_for_template(get_preset(c)) for c in categories}
    category_schemas = {c.id: serialize_schema(get_category_schema(c.name)) for c in categories}
    category_schemas_by_key = {
        c.name.strip().lower().replace(" ", "_"): serialize_schema(get_category_schema(c.name))
        for c in categories
    }
    other_preset = _build_preset_for_template(get_preset("other"))
    google_maps_api_key = current_app.config.get("GOOGLE_MAPS_API_KEY")
    return render_template(
        "resident/report_incident.html",
        similar_incidents=similar,
        categories=categories,
        saved_address=saved_address,
        category_presets=category_presets,
        category_schemas=category_schemas,
        category_schemas_by_key=category_schemas_by_key,
        other_preset=other_preset,
        google_maps_api_key=google_maps_api_key,
    )


@resident_bp.route("/incidents")
@login_required
@role_required(Roles.RESIDENT)
def my_incidents():
    status_param = request.args.get("status")
    category_id_raw = request.args.get("category_id") or ""
    q = request.args.get("q") or ""
    area = request.args.get("area") or ""
    date_from_raw = request.args.get("date_from") or ""
    date_to_raw = request.args.get("date_to") or ""
    page_raw = request.args.get("page") or "1"

    try:
        page = int(page_raw)
    except ValueError:
        page = 1

    status_filter = None
    if status_param:
        try:
            status_filter = IncidentStatus(status_param)
        except ValueError:
            pass

    category_id: int | None = None
    if category_id_raw:
        try:
            category_id = int(category_id_raw)
        except ValueError:
            category_id = None

    date_from = None
    date_to = None
    if date_from_raw:
        try:
            date_from = datetime.fromisoformat(date_from_raw)
        except ValueError:
            date_from = None
    if date_to_raw:
        try:
            # Interpret date_to as end-of-day for inclusive filtering.
            dt = datetime.fromisoformat(date_to_raw)
            date_to = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        except ValueError:
            date_to = None

    page_obj = incident_service.search_incidents_for_resident(
        current_user,  # type: ignore[arg-type]
        status=status_filter,
        category_id=category_id,
        q=q or None,
        date_from=date_from,
        date_to=date_to,
        area=area or None,
        page=page,
        per_page=20,
    )

    categories = (
        db.session.query(IncidentCategory)
        .filter(IncidentCategory.is_active.is_(True))
        .order_by(IncidentCategory.name)
        .all()
    )
    first_day_this_month = date.today().replace(day=1).strftime("%Y-%m-%d")
    return render_template(
        "resident/my_incidents.html",
        page=page_obj,
        selected_status=status_param or "",
        selected_category_id=category_id_raw,
        q=q,
        area=area,
        date_from=date_from_raw,
        date_to=date_to_raw,
        categories=categories,
        first_day_this_month=first_day_this_month,
    )


@resident_bp.route("/incidents/map")
@login_required
@role_required(Roles.RESIDENT)
def incidents_map():
    """Community map for residents: show nearby/public incidents plus own incidents."""
    area = (request.args.get("area") or "").strip()
    status_param = (request.args.get("status") or "").strip()
    category_id_raw = (request.args.get("category_id") or "").strip()
    resolution_param = (request.args.get("resolution") or "").strip().lower()
    my_only = (request.args.get("my_only") or "").strip().lower() in {"1", "true", "on", "yes"}

    status_filter = None
    if status_param:
        try:
            status_filter = IncidentStatus(status_param)
        except ValueError:
            status_filter = None

    category_id: int | None = None
    if category_id_raw:
        try:
            category_id = int(category_id_raw)
        except ValueError:
            category_id = None

    stmt = db.session.query(Incident)
    if my_only:
        stmt = stmt.filter(Incident.reported_by_id == current_user.id)
    else:
        stmt = stmt.filter(
            (Incident.status != IncidentStatus.REJECTED.value)
            | (Incident.reported_by_id == current_user.id)
        )
    if area:
        area_like = f"%{area.lower()}%"
        stmt = stmt.filter(
            or_(
                func.lower(Incident.suburb).like(area_like),
                func.lower(Incident.ward).like(area_like),
                func.lower(Incident.suburb_or_ward).like(area_like),
            )
        )
    if status_filter is not None:
        stmt = stmt.filter(Incident.status == status_filter.value)
    if category_id is not None:
        stmt = stmt.filter(Incident.category_id == category_id)
    resolved_statuses = {
        IncidentStatus.RESOLVED.value,
        IncidentStatus.CLOSED.value,
        IncidentStatus.REJECTED.value,
    }
    if resolution_param == "resolved":
        stmt = stmt.filter(Incident.status.in_(resolved_statuses))
    elif resolution_param == "unresolved":
        stmt = stmt.filter(~Incident.status.in_(resolved_statuses))

    incidents = stmt.order_by(Incident.created_at.desc()).limit(300).all()

    incident_points = []
    for inc in incidents:
        is_own = inc.reported_by_id == current_user.id
        has_coords = inc.latitude is not None and inc.longitude is not None
        is_resolved = (inc.status or "").strip().lower() in resolved_statuses
        incident_points.append(
            {
                "id": inc.id,
                "title": inc.title,
                "status": inc.status,
                "is_resolved": is_resolved,
                "category": inc.category,
                "location": inc.location,
                "suburb_or_ward": inc.suburb_or_ward,
                "created_at": inc.created_at.strftime("%Y-%m-%d %H:%M") if inc.created_at else "",
                "latitude": float(inc.latitude) if has_coords else None,
                "longitude": float(inc.longitude) if has_coords else None,
                "is_own": is_own,
                "detail_url": url_for("resident.incident_detail", incident_id=inc.id)
                if is_own
                else None,
                "reference_code": inc.reference_code or f"#{inc.id}",
            }
        )

    categories = (
        db.session.query(IncidentCategory)
        .filter(IncidentCategory.is_active.is_(True))
        .order_by(IncidentCategory.name)
        .all()
    )
    areas = incident_service.incident_repo.list_distinct_areas()

    return render_template(
        "resident/incidents_map.html",
        incident_points=incident_points,
        categories=categories,
        areas=areas,
        selected_area=area,
        selected_status=status_param,
        selected_resolution=resolution_param,
        selected_category_id=category_id_raw,
        my_only=my_only,
        google_maps_api_key=current_app.config.get("GOOGLE_MAPS_API_KEY"),
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
    normalized_status = str(getattr(incident, "status", "")).strip().lower()
    can_add_additional_evidence = normalized_status == IncidentStatus.AWAITING_EVIDENCE.value
    timeline = incident_service.assemble_timeline(incident_id)
    return render_template(
        "resident/incident_detail.html",
        incident=incident,
        updates=updates,
        timeline=timeline,
        media=media,
        can_edit=can_edit,
        can_add_additional_evidence=can_add_additional_evidence,
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
