from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import abort
from flask_login import current_user, login_required

from app.constants import Roles


def role_required(*allowed_roles: Roles) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Restrict access to users with one of the given roles."""

    def decorator(view_func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view_func)
        @login_required
        def wrapped_view(*args: Any, **kwargs: Any) -> Any:
            if current_user.is_anonymous:
                abort(403)

            if allowed_roles and getattr(current_user, "role", None) not in {
                role.value for role in allowed_roles
            }:
                abort(403)
            return view_func(*args, **kwargs)

        return wrapped_view

    return decorator

