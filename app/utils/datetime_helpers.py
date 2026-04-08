"""Timezone-aware UTC datetime helpers (replaces deprecated datetime.utcnow())."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return current time in UTC (timezone-aware). Use for DB column defaults."""
    return datetime.now(UTC)


def utc_now_naive() -> datetime:
    """Naive UTC instant for legacy DateTime columns (no tzinfo) e.g. SQLite round-trips."""
    return datetime.now(UTC).replace(tzinfo=None)


def is_past_utc(expires_at: datetime | None) -> bool:
    """True if *expires_at* is None or not after now (handles naive vs aware safely)."""
    if expires_at is None:
        return True
    now = datetime.now(UTC)
    exp = expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    return exp <= now
