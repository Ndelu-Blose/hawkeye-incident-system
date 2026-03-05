from __future__ import annotations


def render_status_badge(status: object) -> str:
    """Return a simple badge label for incident status."""
    status_map = {
        "open": "Open",
        "in_progress": "In Progress",
        "resolved": "Resolved",
        "closed": "Closed",
    }

    key = str(status).strip().lower()
    return status_map.get(key, str(status))
