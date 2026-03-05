from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.constants import Roles
from app.services.incident_service import incident_service
from app.utils.decorators import role_required

resident_bp = Blueprint("resident", __name__, template_folder="../templates/resident")


@resident_bp.route("/incidents/new", methods=["GET", "POST"])
@login_required
@role_required(Roles.RESIDENT)
def report_incident():
    if request.method == "POST":
        payload = request.form.to_dict()
        incident, errors = incident_service.create_incident(payload, current_user)  # type: ignore[arg-type]

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("resident/report_incident.html", form_data=payload)

        flash("Incident reported successfully.", "success")
        return redirect(url_for("resident.my_incidents"))

    return render_template("resident/report_incident.html")


@resident_bp.route("/incidents")
@login_required
@role_required(Roles.RESIDENT)
def my_incidents():
    incidents = incident_service.list_incidents_for_resident(current_user)  # type: ignore[arg-type]
    return render_template("resident/my_incidents.html", incidents=incidents)


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

    # Residents should only see their own incidents
    if incident.reported_by_id != current_user.id:
        flash("You do not have access to that incident.", "danger")
        return redirect(url_for("resident.my_incidents"))

    return render_template(
        "resident/incident_detail.html",
        incident=incident,
        updates=updates,
    )
