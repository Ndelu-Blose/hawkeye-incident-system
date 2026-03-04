from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.constants import IncidentStatus, Roles
from app.services.incident_service import incident_service
from app.services.dashboard_service import dashboard_service
from app.utils.decorators import role_required


authority_bp = Blueprint(
    "authority",
    __name__,
    template_folder="../templates/authority",
)


def _parse_status_filter(raw: str | None) -> IncidentStatus | None:
    if not raw:
        return None
    try:
        return IncidentStatus(raw)
    except ValueError:
        return None


@authority_bp.route("/dashboard")
@login_required
@role_required(Roles.AUTHORITY, Roles.ADMIN)
def dashboard():
    status_param = request.args.get("status") or None
    status_filter = _parse_status_filter(status_param)

    incidents = incident_service.list_incidents_for_authority(status=status_filter)
    overview = dashboard_service.get_overview()

    return render_template(
        "authority/dashboard.html",
        incidents=incidents,
        overview=overview,
        selected_status=status_param,
    )


@authority_bp.route("/incidents/<int:incident_id>")
@login_required
@role_required(Roles.AUTHORITY, Roles.ADMIN)
def incident_detail(incident_id: int):
    incident, updates = incident_service.get_incident_with_history(
        incident_id,
        current_user,  # type: ignore[arg-type]
    )
    if incident is None:
        flash("Incident not found.", "warning")
        return redirect(url_for("authority.dashboard"))

    return render_template(
        "authority/incident_detail.html",
        incident=incident,
        updates=updates,
    )


@authority_bp.route("/incidents/<int:incident_id>/status", methods=["POST"])
@login_required
@role_required(Roles.AUTHORITY, Roles.ADMIN)
def update_incident_status(incident_id: int):
    to_status_raw = request.form.get("status") or ""
    note = request.form.get("note") or ""

    try:
        to_status = IncidentStatus(to_status_raw)
    except ValueError:
        flash("Invalid status.", "danger")
        return redirect(url_for("authority.incident_detail", incident_id=incident_id))

    ok, errors = incident_service.update_status(
        incident_id=incident_id,
        to_status=to_status,
        note=note,
        authority_user=current_user,  # type: ignore[arg-type]
    )

    if not ok:
        for error in errors:
            flash(error, "danger")
    else:
        flash("Incident status updated.", "success")

    return redirect(url_for("authority.incident_detail", incident_id=incident_id))

