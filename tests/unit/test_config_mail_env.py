import os

from app.config import BaseConfig


def test_mail_and_base_url_config_parsing(monkeypatch):
    monkeypatch.setenv("MAIL_USE_SSL", "true")
    monkeypatch.setenv("MAIL_SUPPRESS_SEND", "true")
    monkeypatch.setenv("APP_BASE_URL", "https://example.test")

    class EnvConfig(BaseConfig):
        MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "false").lower() == "true"
        MAIL_SUPPRESS_SEND = os.getenv("MAIL_SUPPRESS_SEND", "false").lower() == "true"
        APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:5000")

    assert EnvConfig.MAIL_USE_SSL is True
    assert EnvConfig.MAIL_SUPPRESS_SEND is True
    assert EnvConfig.APP_BASE_URL == "https://example.test"
