"""Helpers for incident list date-range filters (From / To)."""

from __future__ import annotations

from datetime import date, datetime, time


def clamp_incident_list_date_filters(
    date_from: datetime | None,
    date_to: datetime | None,
    *,
    today: date | None = None,
) -> tuple[datetime | None, datetime | None]:
    """
    Incident filters are historical: do not allow a range that extends past today.

    If either bound is after the current calendar day (server local date), it is
    clamped to start-of-day or end-of-day today respectively.
    """
    today = today or date.today()
    start_today = datetime.combine(today, time.min)
    end_today = datetime.combine(today, time(23, 59, 59, 999999))
    if date_from is not None and date_from.date() > today:
        date_from = start_today
    if date_to is not None and date_to.date() > today:
        date_to = end_today
    return date_from, date_to
