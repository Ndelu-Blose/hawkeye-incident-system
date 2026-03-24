from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy.orm import Query

# Ensure the app package is importable when this script is run directly.
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import create_app  # type: ignore  # noqa: E402
from app.extensions import db  # type: ignore  # noqa: E402
from app.models import Incident  # type: ignore  # noqa: E402
from app.services.location_service import location_service  # type: ignore  # noqa: E402


def _iter_incidents_to_backfill(batch_size: int = 100) -> Iterable[Incident]:
    """Yield incidents that are missing validated location information."""
    query: Query[Incident] = (
        db.session.query(Incident)
        .filter(
            (Incident.location_validated.is_(False))
            | (Incident.latitude.is_(None))
            | (Incident.longitude.is_(None))
        )
        .order_by(Incident.id.asc())
    )
    yield from query.yield_per(batch_size)


def _geocode_incident(incident: Incident) -> bool:
    """Attempt to geocode a single incident; return True if it was updated."""
    if not incident.street_or_landmark or not incident.suburb_or_ward:
        return False

    address = f"{incident.street_or_landmark}, {incident.suburb_or_ward}".strip(", ")
    if not address:
        return False

    if not location_service.is_configured():
        # Caller should have checked configuration; this is a safety net.
        return False

    result = location_service.geocode(address)
    if result is None:
        return False

    incident.latitude = result.latitude
    incident.longitude = result.longitude
    incident.validated_address = result.validated_address
    if getattr(result, "suburb", None):
        incident.suburb = result.suburb
    if getattr(result, "ward", None):
        incident.ward = result.ward
    incident.location_validated = True
    incident.location_precision = "exact"
    incident.geocoded_at = datetime.now(UTC)
    incident.geocode_source = "google_maps"
    return True


def main() -> None:
    """Backfill geocoded location fields for existing incidents.

    Usage (example):
        $ export FLASK_ENV=production
        $ export DATABASE_URL=postgresql://...
        $ export GOOGLE_MAPS_API_KEY=...
        $ python scripts/geocode_backfill.py
    """
    env = os.getenv("FLASK_ENV", "production")
    app = create_app(env)
    with app.app_context():
        if not location_service.is_configured():
            print("Location service is not configured. Set GOOGLE_MAPS_API_KEY and retry.")
            return

        updated = 0
        total = 0
        for incident in _iter_incidents_to_backfill():
            total += 1
            if _geocode_incident(incident):
                updated += 1
                if updated % 50 == 0:
                    db.session.flush()
                    print(f"Updated {updated} incidents so far...")

        if updated:
            db.session.commit()
        print(f"Backfill complete. Considered={total}, updated={updated}.")


if __name__ == "__main__":
    main()
