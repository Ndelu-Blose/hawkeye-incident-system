"""Build absolute URLs for emails when APP_BASE_URL is set (Docker, reverse proxies)."""

from __future__ import annotations

from typing import Any

from flask import current_app, url_for


def public_url_for(endpoint: str, **values: Any) -> str:
    """Prefer ``APP_BASE_URL`` + relative path over ``url_for(..., _external=True)``.

    Avoids wrong hosts inside containers and matches the URL users open in the browser
    when ``APP_BASE_URL`` is set (e.g. ``http://127.0.0.1:5005``).
    """
    base = (current_app.config.get("APP_BASE_URL") or "").strip().rstrip("/")
    relative = url_for(endpoint, **values, _external=False)
    if not relative.startswith("/"):
        relative = "/" + relative
    if base:
        return f"{base}{relative}"
    return url_for(endpoint, **values, _external=True)
