from __future__ import annotations

from datetime import timedelta

from markupsafe import Markup


def sla_due(incident: object) -> object:
    """Return incident.reported_at + SLA hours (from category or 72), or None."""
    if incident is None or not getattr(incident, "reported_at", None):
        return None
    reported_at = incident.reported_at
    hours = 72
    if getattr(incident, "category_rel", None) is not None:
        cat = incident.category_rel
        if getattr(cat, "default_sla_hours", None) is not None:
            hours = cat.default_sla_hours
    return reported_at + timedelta(hours=hours)


def render_status_badge(status: object) -> Markup:
    """Return Bootstrap badge HTML for incident status."""
    status_map = {
        "pending": '<span class="badge bg-warning text-dark">Reported</span>',
        "verified": '<span class="badge bg-info text-dark">Verified</span>',
        "assigned": '<span class="badge bg-primary">Assigned</span>',
        "in_progress": '<span class="badge bg-info text-dark">In Progress</span>',
        "resolved": '<span class="badge bg-success">Resolved</span>',
        "rejected": '<span class="badge bg-danger">Rejected</span>',
        "closed": '<span class="badge bg-secondary">Closed</span>',
        "open": '<span class="badge bg-secondary">Open</span>',
    }
    key = str(status).strip().lower()
    html = status_map.get(key, f'<span class="badge bg-secondary">{status}</span>')
    return Markup(html)
