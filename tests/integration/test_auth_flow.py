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
