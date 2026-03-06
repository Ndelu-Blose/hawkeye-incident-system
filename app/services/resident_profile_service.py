"""Resident profile and onboarding: get/create/update profile, completion check."""

from __future__ import annotations

from app.constants import Roles
from app.extensions import db
from app.models import ResidentProfile, User
from app.utils.datetime_helpers import utc_now


def get_or_create_profile(user: User) -> ResidentProfile:
    """Return the resident's profile, creating one if missing (residents only)."""
    if getattr(user, "resident_profile", None) is not None:
        return user.resident_profile
    profile = ResidentProfile(
        user_id=user.id,
        profile_completed=False,
        consent_location=False,
        location_verified=False,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.session.add(profile)
    db.session.commit()
    return profile


def is_profile_complete(user: User) -> bool:
    """True if user has a completed resident profile (required to report incidents)."""
    if getattr(user, "role", None) != Roles.RESIDENT.value:
        return True
    profile = getattr(user, "resident_profile", None)
    if profile is None:
        return False
    if not profile.profile_completed:
        return False
    phone = (profile.phone_number or "").strip()
    street = (profile.street_address_1 or "").strip()
    suburb = (profile.suburb or "").strip()
    if not phone or not street or not suburb:
        return False
    if not profile.consent_location:
        return False
    return True


def update_profile(
    user: User,
    payload: dict,
) -> tuple[ResidentProfile | None, list[str]]:
    """Update resident profile; set profile_completed only when all required fields + consent."""
    errors: list[str] = []
    profile = get_or_create_profile(user)
    phone = (payload.get("phone_number") or "").strip()
    street = (payload.get("street_address_1") or "").strip()
    street2 = (payload.get("street_address_2") or "").strip()
    suburb = (payload.get("suburb") or "").strip()
    city = (payload.get("city") or "").strip()
    postal_code = (payload.get("postal_code") or "").strip() or None
    consent = payload.get("consent_location") in (True, "true", "1", "on", "yes")
    municipality_id = payload.get("municipality_id")
    district_id = payload.get("district_id")
    ward_id = payload.get("ward_id")
    lat = payload.get("latitude")
    lng = payload.get("longitude")

    profile.phone_number = phone or None
    profile.street_address_1 = street or None
    profile.street_address_2 = street2 or None
    profile.suburb = suburb or None
    profile.city = city or None
    profile.postal_code = postal_code
    profile.consent_location = consent

    if municipality_id not in (None, ""):
        try:
            profile.municipality_id = int(municipality_id)
        except (TypeError, ValueError):
            profile.municipality_id = None
    else:
        profile.municipality_id = None

    if district_id not in (None, ""):
        try:
            profile.district_id = int(district_id)
        except (TypeError, ValueError):
            profile.district_id = None
    else:
        profile.district_id = None

    if ward_id not in (None, ""):
        try:
            profile.ward_id = int(ward_id)
        except (TypeError, ValueError):
            profile.ward_id = None
    else:
        profile.ward_id = None

    if lat is not None and lng is not None:
        try:
            profile.latitude = float(lat)
            profile.longitude = float(lng)
        except (TypeError, ValueError):
            pass

    completed = bool(phone and street and suburb and consent)
    profile.profile_completed = completed
    profile.updated_at = utc_now()
    db.session.commit()
    return profile, errors
