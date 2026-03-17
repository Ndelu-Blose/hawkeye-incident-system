from __future__ import annotations

from dataclasses import dataclass

from flask import current_app


@dataclass
class GeocodedLocation:
    """Normalized location result returned by the location service."""

    latitude: float
    longitude: float
    validated_address: str
    suburb: str | None = None
    ward: str | None = None


class LocationService:
    """Thin wrapper around Google Maps (or other provider) for geocoding.

    For now this is intentionally minimal; in development and tests it can safely
    operate in a no-op mode when no API key is configured.
    """

    def __init__(self, api_key: str | None = None) -> None:
        # Avoid touching current_app when no application context is active (e.g. import time in tests).
        if api_key is None:
            try:
                api_key = current_app.config.get("GOOGLE_MAPS_API_KEY")  # type: ignore[attr-defined]
            except Exception:
                api_key = None
        self.api_key = api_key

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def geocode(self, address: str) -> GeocodedLocation | None:
        """Forward geocode a free-text address into structured coordinates.

        In this initial implementation we return None when no API key is set.
        A future version can call the real Google Maps API and map the response.
        """
        if not self.is_configured() or not address.strip():
            return None
        # Placeholder: real provider integration will be added in a later Phase 2 step.
        return None

    def reverse_geocode(self, latitude: float, longitude: float) -> GeocodedLocation | None:
        """Reverse geocode coordinates into a structured address."""
        if not self.is_configured():
            return None
        # Placeholder for future integration.
        return None


location_service = LocationService()
