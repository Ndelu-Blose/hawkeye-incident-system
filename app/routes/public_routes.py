"""Public routes: anonymised area incident view (no login required)."""

from __future__ import annotations

from flask import Blueprint, current_app, render_template, request

from app.repositories.incident_repo import IncidentRepository

public_bp = Blueprint("public", __name__, url_prefix="/public")


@public_bp.route("/area")
def area_incidents():
    """Public anonymised, map-first incident preview by area."""
    incident_repo = IncidentRepository()
    area = (request.args.get("area") or "").strip()
    view_mode = "area" if area else "recent"

    areas = incident_repo.list_distinct_areas()
    if view_mode == "area":
        incidents = incident_repo.search_public(area=area, page=1, per_page=150).items
    else:
        incidents = incident_repo.list_recent(limit=80, load_relations=True)
        incidents = [i for i in incidents if (i.status or "").strip().lower() != "rejected"]

    incidents = sorted(incidents, key=lambda i: i.created_at or 0, reverse=True)
    map_points = [
        {
            "id": inc.id,
            "title": inc.title,
            "category": (
                inc.category_rel.name
                if getattr(inc, "category_rel", None) is not None
                else inc.category
            ),
            "status": inc.status,
            "lat": float(inc.latitude),
            "lng": float(inc.longitude),
            "reported_on": inc.created_at.strftime("%Y-%m-%d") if inc.created_at else "",
            "area": inc.suburb_or_ward or inc.suburb or inc.ward or "",
            "reference_code": inc.reference_code or f"#{inc.id}",
        }
        for inc in incidents
        if inc.latitude is not None and inc.longitude is not None
    ]
    list_items = incidents[:8]

    return render_template(
        "public/area_incidents.html",
        area=area,
        areas=areas,
        incidents=list_items,
        map_points=map_points,
        google_maps_api_key=current_app.config.get("GOOGLE_MAPS_API_KEY"),
        view_mode=view_mode,
    )
