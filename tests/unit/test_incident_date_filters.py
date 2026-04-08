"""Tests for incident list date filter clamping."""

from datetime import date, datetime, time

from app.utils.incident_date_filters import clamp_incident_list_date_filters


def test_clamp_leaves_past_unchanged():
    d0 = date(2025, 1, 10)
    date_from = datetime.combine(d0, time.min)
    date_to = datetime.combine(d0, time(23, 59, 59, 999999))
    f, t = clamp_incident_list_date_filters(date_from, date_to, today=date(2026, 4, 7))
    assert f == date_from
    assert t == date_to


def test_clamp_future_from_to_today_start():
    today = date(2026, 4, 7)
    future = datetime.combine(date(2027, 1, 1), time.min)
    f, t = clamp_incident_list_date_filters(future, None, today=today)
    assert f == datetime.combine(today, time.min)
    assert t is None


def test_clamp_future_to_to_today_end():
    today = date(2026, 4, 7)
    future = datetime.combine(date(2028, 12, 31), time(23, 59, 59, 999999))
    f, t = clamp_incident_list_date_filters(None, future, today=today)
    assert f is None
    assert t == datetime.combine(today, time(23, 59, 59, 999999))
