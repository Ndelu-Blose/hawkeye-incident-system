from datetime import timedelta

from app.services.auth_service import auth_service
from app.utils.datetime_helpers import is_past_utc, utc_now_naive


def test_is_past_utc_naive_future(app):
    future = utc_now_naive() + timedelta(days=400)
    assert is_past_utc(future) is False


def test_verify_email_token_round_trip(app):
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Verify Me",
            email="verify-me@example.com",
            password="password123",
            email_verified=False,
        )
        assert user is not None
        assert user.email_verification_token
        token = user.email_verification_token

        ok, errors = auth_service.verify_email_token(token)
        assert ok is True
        assert not errors

        user2 = auth_service.user_repo.get_by_email("verify-me@example.com")
        assert user2 is not None
        assert user2.email_verified is True
        assert user2.email_verification_token is None


def test_authenticate_blocks_unverified_when_required(app):
    app.config["EMAIL_VERIFICATION_REQUIRED"] = True
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Unverified",
            email="unverified@example.com",
            password="password123",
            email_verified=False,
        )
        assert user is not None
        u, errors = auth_service.authenticate("unverified@example.com", "password123")
        assert u is None
        assert any("verify" in e.lower() for e in errors)
