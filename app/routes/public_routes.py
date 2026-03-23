"""Public routes: anonymised area incident view (no login required)."""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, render_template, request

from app.extensions import db
from app.models import IncidentCategory
from app.repositories.incident_repo import IncidentRepository

public_bp = Blueprint("public", __name__, url_prefix="/public")


@public_bp.route("/area")
def area_incidents():
    """Public anonymised incident list by area. No reporter or PII exposed."""
    incident_repo = IncidentRepository()
    area = (request.args.get("area") or "").strip()
    category_id_raw = request.args.get("category_id")
    status = request.args.get("status") or ""
    date_from_raw = request.args.get("date_from")
    date_to_raw = request.args.get("date_to")
    page = request.args.get("page", 1, type=int)

    categories = (
        db.session.query(IncidentCategory)
        .filter(IncidentCategory.is_active.is_(True))
        .order_by(IncidentCategory.name)
        .all()
    )

    areas = incident_repo.list_distinct_areas()

    date_from = None
    date_to = None
    if date_from_raw:
        try:
            date_from = datetime.strptime(date_from_raw, "%Y-%m-%d")
        except ValueError:
            pass
    if date_to_raw:
        try:
            date_to = datetime.strptime(date_to_raw, "%Y-%m-%d")
        except ValueError:
            pass

    category_id = None
    if category_id_raw:
        try:
            category_id = int(category_id_raw)
        except (TypeError, ValueError):
            pass

    if area:
        page_result = incident_repo.search_public(
            area=area,
            category_id=category_id if category_id else None,
            status=status if status else None,
            date_from=date_from,
            date_to=date_to,
            page=page,
            per_page=20,
        )
        incidents = page_result.items
    else:
        page_result = None
        incidents = []

    return render_template(
        "public/area_incidents.html",
        area=area,
        areas=areas,
        categories=categories,
        incidents=incidents,
        page_result=page_result,
        selected_category_id=category_id,
        selected_status=status,
        date_from=date_from_raw or "",
        date_to=date_to_raw or "",
    )
