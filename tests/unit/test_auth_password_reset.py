from app.services.auth_service import auth_service


def test_request_password_reset_by_email_is_anti_enumeration_for_unknown_email(app):
    with app.app_context():
        ok, errors = auth_service.request_password_reset_by_email("unknown@example.com")
        assert ok is True
        assert errors == []


def test_request_password_reset_by_email_creates_token_for_existing_user(app, monkeypatch):
    monkeypatch.setattr(
        "app.services.auth_service.send_outbound_email",
        lambda *_a, **_k: (True, None, "smtp"),
    )
    with app.app_context():
        user, errors = auth_service.register_user(
            name="Password Reset User",
            email="password-reset-user@example.com",
            password="password123",
            email_verified=True,
        )
        assert user is not None
        assert errors == []
        assert user.invite_token is None

        with app.test_request_context():
            ok, reset_errors = auth_service.request_password_reset_by_email(user.email)
        assert ok is True
        assert reset_errors == []

        refreshed = auth_service.user_repo.get_by_email(user.email)
        assert refreshed is not None
        assert refreshed.invite_token is not None
        assert refreshed.invite_expires_at is not None
