from app.utils.validators import validate_login_form, validate_registration_form


def test_registration_validator_min_requirements():
    data = {
        "name": "Test User",
        "email": "user@example.com",
        "password": "password123",
        "password_confirm": "password123",
    }
    errors = validate_registration_form(data)
    assert errors == []


def test_login_validator_requires_email_and_password():
    errors = validate_login_form({"email": "", "password": ""})
    assert "Email is required." in errors
    assert "Password is required." in errors
