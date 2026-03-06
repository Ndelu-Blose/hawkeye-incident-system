from __future__ import annotations

from markupsafe import Markup


def render_status_badge(status: object) -> Markup:
    """Return Bootstrap badge HTML for incident status."""
    status_map = {
        "pending": '<span class="badge bg-warning text-dark">Pending</span>',
        "in_progress": '<span class="badge bg-info text-dark">In Progress</span>',
        "resolved": '<span class="badge bg-success">Resolved</span>',
        "rejected": '<span class="badge bg-danger">Rejected</span>',
        "open": '<span class="badge bg-secondary">Open</span>',
        "closed": '<span class="badge bg-secondary">Closed</span>',
    }
    key = str(status).strip().lower()
    html = status_map.get(key, f'<span class="badge bg-secondary">{status}</span>')
    return Markup(html)
