"""Public routes: anonymised area incident view (no login required)."""

from __future__ import annotations

from flask import Blueprint, render_template, request

from app.repositories.incident_repo import IncidentRepository

public_bp = Blueprint("public", __name__, url_prefix="/public")


@public_bp.route("/area")
def area_incidents():
    """Public anonymised incident list by area (no login required)."""
    incident_repo = IncidentRepository()
    area = (request.args.get("area") or "").strip()

    areas = incident_repo.list_distinct_areas()
    if area:
        incidents = incident_repo.search_public(area=area, page=1, per_page=150).items
    else:
        incidents = incident_repo.list_recent(limit=80, load_relations=True)
        incidents = [i for i in incidents if (i.status or "").strip().lower() != "rejected"]

    incidents = sorted(incidents, key=lambda i: i.created_at or 0, reverse=True)
    list_items = incidents[:50]

    return render_template(
        "public/area_incidents.html",
        area=area,
        areas=areas,
        incidents=list_items,
    )
