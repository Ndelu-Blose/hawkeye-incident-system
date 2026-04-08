from app.services.auth_service import auth_service


def test_register_and_login_flow(client):
    resp = client.post(
        "/auth/register",
        data={
            "name": "Test User",
            "email": "user@example.com",
            "password": "password123",
            "password_confirm": "password123",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


def test_forgot_password_uses_generic_success_message(client, app, monkeypatch):
    monkeypatch.setattr(
        "app.services.auth_service.send_outbound_email",
        lambda *_a, **_k: (True, None, "smtp"),
    )
    with app.app_context():
        user, errors = auth_service.register_user(
            name="Reset User",
            email="reset-user@example.com",
            password="password123",
            email_verified=True,
        )
        assert user is not None
        assert errors == []

    resp = client.post(
        "/auth/forgot-password",
        data={"email": "reset-user@example.com"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"request has been received" in resp.data.lower()
    assert b"sent password reset instructions" not in resp.data.lower()


def test_forgot_password_keeps_anti_enumeration_for_unknown_email(client):
    resp = client.post(
        "/auth/forgot-password",
        data={"email": "unknown@example.com"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"request has been received" in resp.data.lower()


def test_resend_verification_uses_generic_success_message(client, app, monkeypatch):
    monkeypatch.setattr(
        "app.services.auth_service.send_outbound_email",
        lambda *_a, **_k: (True, None, "smtp"),
    )
    with app.app_context():
        user, errors = auth_service.register_user(
            name="Needs Verify",
            email="needs-verify@example.com",
            password="password123",
            email_verified=False,
        )
        assert user is not None
        assert errors == []

    resp = client.post(
        "/auth/resend-verification",
        data={"email": "needs-verify@example.com"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"request has been received" in resp.data.lower()
    assert b"we sent a new email" not in resp.data.lower()


def test_register_and_login_reject_invalid_email_format(client):
    bad_register = client.post(
        "/auth/register",
        data={
            "name": "Bad Email",
            "email": "invalid-email",
            "password": "password123",
            "password_confirm": "password123",
        },
        follow_redirects=True,
    )
    assert bad_register.status_code == 200
    assert b"valid email" in bad_register.data.lower()

    bad_login = client.post(
        "/auth/login",
        data={"email": "invalid-email", "password": "password123"},
        follow_redirects=True,
    )
    assert bad_login.status_code == 200
    assert (
        b"valid email" in bad_login.data.lower()
        or b"invalid email or password" in bad_login.data.lower()
    )

    resp = client.post(
        "/auth/login",
        data={"email": "user@example.com", "password": "password123"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
