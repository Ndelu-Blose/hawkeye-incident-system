from app.constants import Roles
from app.extensions import db
from app.models.resident_profile import ResidentProfile
from app.services.auth_service import auth_service
from app.services.resident_profile_service import (
    get_or_create_profile,
    profile_completion_snapshot,
    update_profile,
)


def test_profile_completion_snapshot_reports_pending_then_verified(app):
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="profile-snapshot@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        profile = get_or_create_profile(user)
        pending = profile_completion_snapshot(profile)
        assert pending["percentage"] == 0
        assert pending["status_label"] == "Pending"

        profile.phone_number = "0812345678"
        profile.street_address_1 = "123 Main"
        profile.suburb = "Amanzimtoti"
        profile.consent_location = True
        profile.profile_completed = True
        db.session.commit()

        verified = profile_completion_snapshot(profile)
        assert verified["percentage"] == 100
        assert verified["status_label"] == "Verified"
        assert verified["is_verified"] is True


def test_update_profile_persists_notification_and_analytics_preferences(app):
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="profile-prefs@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        profile, errors = update_profile(
            user,
            {
                "phone_number": "0811111111",
                "street_address_1": "140229 Nkanyisweni",
                "suburb": "Amanzimtoti",
                "city": "Durban",
                "consent_location": "1",
                "share_anonymous_analytics": "1",
                "notify_incident_updates": "1",
                "notify_status_changes": "1",
                "notify_community_alerts": "1",
                "avatar_filename": "avatar.png",
            },
        )
        assert not errors
        assert profile is not None
        refreshed = db.session.get(ResidentProfile, profile.id)
        assert refreshed is not None
        assert refreshed.share_anonymous_analytics is True
        assert refreshed.notify_incident_updates is True
        assert refreshed.notify_status_changes is True
        assert refreshed.notify_community_alerts is True
        assert refreshed.avatar_filename == "avatar.png"
