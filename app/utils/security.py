from __future__ import annotations

from urllib.parse import urljoin, urlparse

from flask import request

from app.extensions import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.generate_password_hash(password).decode("utf-8")


def check_password(password: str, password_hash: str) -> bool:
    return bcrypt.check_password_hash(password_hash, password)


def is_safe_url(target: str) -> bool:
    """Ensure the redirect target is relative or same-origin."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


def safe_redirect_target(default: str = "/") -> str:
    target = request.args.get("next")
    if target and is_safe_url(target):
        return target
    return default
