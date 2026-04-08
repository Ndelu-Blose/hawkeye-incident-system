from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.constants import IncidentStatus, Roles
from app.services.dashboard_service import dashboard_service
from app.services.incident_service import incident_service
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


def _get_user_authority_id(user):
    """First authority_id for authority users, None for admins."""
    memberships = list(getattr(user, "authority_memberships", []) or [])
    if memberships:
        return memberships[0].authority_id
    return None


@authority_bp.route("/dashboard")
@login_required
@role_required(Roles.AUTHORITY, Roles.ADMIN)
def dashboard():
    status_param = request.args.get("status") or None
    status_filter = _parse_status_filter(status_param)
    authority_id = _get_user_authority_id(current_user)

    queue = None
    if authority_id and status_param:
        if status_param == "assigned":
            queue = "incoming"
        elif status_param == "acknowledged":
            queue = "acknowledged"
        elif status_param == "in_progress":
            queue = "in_progress"
        elif status_param in ("resolved", "closed"):
            queue = "completed"

    overview = dashboard_service.get_overview()
    incidents = dashboard_service.get_authority_incident_list(
        status=status_filter,
        authority_id=authority_id,
        queue=queue,
        limit=200,
    )

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

    can_acknowledge = incident_service.can_acknowledge_incident(
        incident_id,
        current_user,  # type: ignore[arg-type]
    )
    workflow_actions = incident_service.get_authority_workflow_actions(incident)

    return render_template(
        "authority/incident_detail.html",
        incident=incident,
        updates=updates,
        timeline=incident_service.assemble_timeline(incident_id),
        can_acknowledge=can_acknowledge,
        workflow_actions=workflow_actions,
    )


@authority_bp.route("/incidents/<int:incident_id>/acknowledge", methods=["POST"])
@login_required
@role_required(Roles.AUTHORITY, Roles.ADMIN)
def acknowledge_incident(incident_id: int):
    """Acknowledge a dispatched incident (assigned -> acknowledged)."""
    note = (request.form.get("note") or "").strip() or None
    ok, errors = incident_service.acknowledge_incident(
        incident_id=incident_id,
        actor_user=current_user,  # type: ignore[arg-type]
        note=note,
    )
    if not ok:
        for error in errors:
            flash(error, "danger")
    else:
        flash("Incident acknowledged.", "success")
    return redirect(url_for("authority.incident_detail", incident_id=incident_id))


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

    incident = incident_service.incident_repo.get_by_id(incident_id)
    if incident is None:
        flash("Incident not found.", "warning")
        return redirect(url_for("authority.dashboard"))

    # Receipt must use acknowledge_incident so dispatch ack + incident event stay aligned.
    if to_status == IncidentStatus.ACKNOWLEDGED:
        flash(
            "Use “Acknowledge incident” above to confirm receipt—that updates dispatch and status together.",
            "warning",
        )
        return redirect(url_for("authority.incident_detail", incident_id=incident_id))

    actions = incident_service.get_authority_workflow_actions(incident)
    allowed = {a["status"] for a in actions}
    if to_status.value not in allowed:
        flash(
            "That status is set automatically by the system or by your admin team—not from this form.",
            "warning",
        )
        return redirect(url_for("authority.incident_detail", incident_id=incident_id))

    meta = next((a for a in actions if a["status"] == to_status.value), None)
    if meta and meta.get("note_required") and not (note or "").strip():
        flash("A note is required for this action.", "warning")
        return redirect(url_for("authority.incident_detail", incident_id=incident_id))

    ok, errors = incident_service.update_status(
        incident_id=incident_id,
        to_status=to_status,
        note=note,
        authority_user=current_user,  # type: ignore[arg-type]
        allow_admin_override=False,
    )

    if not ok:
        for error in errors:
            flash(error, "danger")
    else:
        flash("Incident status updated.", "success")

    return redirect(url_for("authority.incident_detail", incident_id=incident_id))
