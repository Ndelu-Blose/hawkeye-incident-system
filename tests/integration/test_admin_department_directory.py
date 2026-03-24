from app.constants import Roles
from app.services.auth_service import auth_service
from scripts.seed_departments import seed_departments


def _seed_admin():
    auth_service.register_user(
        name="Admin Directory",
        email="admin-directory@example.com",
        password="password123",
        role=Roles.ADMIN.value,
    )


def test_admin_department_directory_renders(app, client):
    with app.app_context():
        _seed_admin()
        seed_departments()

    client.post(
        "/auth/login",
        data={"email": "admin-directory@example.com", "password": "password123"},
        follow_redirects=True,
    )
    response = client.get("/admin/departments/directory")
    assert response.status_code == 200
    assert b"Department Directory" in response.data
    assert b"METRO_POLICE" in response.data
    assert b"metroceo@durban.gov.za" in response.data


def test_admin_department_directory_filters_by_channel(app, client):
    with app.app_context():
        _seed_admin()
        seed_departments()

    client.post(
        "/auth/login",
        data={"email": "admin-directory@example.com", "password": "password123"},
        follow_redirects=True,
    )
    response = client.get("/admin/departments/directory?channel=email")
    assert response.status_code == 200
    assert b"Department Directory" in response.data
    assert b"email:" in response.data
