from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import abort
from flask_login import current_user, login_required

from app.constants import Roles


def _norm_role(value: Any) -> str:
    raw = getattr(value, "value", value)
    if raw is None:
        return ""

    s = str(raw).strip()

    # Handle strings like "Roles.AUTHORITY"
    if "." in s:
        s = s.split(".")[-1]

    s_lower = s.lower()

    # Handle enum-name strings like "AUTHORITY" / "ADMIN"
    try:
        member = Roles[s.upper()]  # type: ignore[index]
        return str(getattr(member, "value", s_lower)).strip().lower()
    except Exception:
        return s_lower


def role_required(*allowed_roles: Roles) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Restrict access to users with one of the given roles."""

    def decorator(view_func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view_func)
        @login_required
        def wrapped_view(*args: Any, **kwargs: Any) -> Any:
            if current_user.is_anonymous:
                abort(403)

            if allowed_roles:
                allowed_normalized = {_norm_role(role) for role in allowed_roles}
                user_role = _norm_role(getattr(current_user, "role", ""))
                if user_role not in allowed_normalized:
                    abort(403)

            return view_func(*args, **kwargs)

        return wrapped_view

    return decorator
