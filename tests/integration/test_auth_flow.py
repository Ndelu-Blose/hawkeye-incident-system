from app import create_app


def test_register_and_login_flow():
    app = create_app("testing")
    client = app.test_client()

    with app.app_context():
        # Register
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

        # Login
        resp = client.post(
            "/auth/login",
            data={
                "email": "user@example.com",
                "password": "password123",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

