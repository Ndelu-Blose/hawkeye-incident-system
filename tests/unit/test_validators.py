from app.utils.validators import (
    validate_email_format,
    validate_login_form,
    validate_registration_form,
)


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


def test_email_format_validator_rejects_invalid_inputs():
    assert validate_email_format("missing-at.example.com") is not None
    assert validate_email_format("a b@example.com") is not None
    assert validate_email_format("user@example") is not None
    assert validate_email_format("user@@example.com") is not None


def test_email_format_validator_accepts_reasonable_email():
    assert validate_email_format("valid.user@example.com") is None
