import os
from datetime import timedelta


class BaseConfig:
    """Shared configuration for all environments."""

    APP_NAME = "Alertweb Solutions"
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # Mail
    MAIL_SERVER = os.getenv("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "25"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "false").lower() == "true"
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_SUPPRESS_SEND = os.getenv("MAIL_SUPPRESS_SEND", "false").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv(
        "MAIL_DEFAULT_SENDER",
        "alertweb@example.com",
    )
    APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:5000")

    # Email verification (Resend API — https://resend.com/docs/send-with-python)
    RESEND_API_KEY = (os.getenv("RESEND_API_KEY") or "").strip() or None
    _raw_from = (os.getenv("RESEND_FROM_EMAIL") or "").strip().strip('"').strip("'")
    RESEND_FROM_EMAIL = _raw_from or None
    EMAIL_VERIFICATION_TOKEN_DAYS = int(os.getenv("EMAIL_VERIFICATION_TOKEN_DAYS", "7"))
    # When true, unverified users cannot log in (disabled in tests via TestingConfig).
    EMAIL_VERIFICATION_REQUIRED = os.getenv("EMAIL_VERIFICATION_REQUIRED", "true").lower() == "true"

    # Rate limiting
    RATELIMIT_DEFAULT = "200 per day"
    RATELIMIT_STORAGE_URI = "memory://"

    # Google Maps (Places Autocomplete, map pin for incident location)
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

    # Uploads (evidence images)
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "instance/uploads")
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB total request
    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB per image
    MAX_MEDIA_PER_INCIDENT = 5

    # Dispatch auto-escalation reminders
    DISPATCH_AUTO_ESCALATION_ENABLED = (
        os.getenv("DISPATCH_AUTO_ESCALATION_ENABLED", "true").lower() == "true"
    )
    DISPATCH_REMINDER_STALE_MINUTES = int(os.getenv("DISPATCH_REMINDER_STALE_MINUTES", "60"))
    DISPATCH_REMINDER_RETRY_COOLDOWN_MINUTES = int(
        os.getenv("DISPATCH_REMINDER_RETRY_COOLDOWN_MINUTES", "30")
    )
    DISPATCH_MAX_REMINDERS = int(os.getenv("DISPATCH_MAX_REMINDERS", "3"))


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    ENV = "development"


class TestingConfig(BaseConfig):
    TESTING = True
    ENV = "testing"
    EMAIL_VERIFICATION_REQUIRED = False
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "TEST_DATABASE_URL",
        "sqlite:///:memory:",
    )
    WTF_CSRF_ENABLED = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    ENV = "production"

    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Strict"
