"""Timezone-aware UTC datetime helpers (replaces deprecated datetime.utcnow())."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return current time in UTC (timezone-aware). Use for DB column defaults."""
    return datetime.now(UTC)
