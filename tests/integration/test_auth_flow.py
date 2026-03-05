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

    resp = client.post(
        "/auth/login",
        data={"email": "user@example.com", "password": "password123"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
