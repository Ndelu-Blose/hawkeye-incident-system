def test_public_url_for_uses_app_base_url_when_set(app):
    app.config["APP_BASE_URL"] = "https://example.test"
    with app.test_request_context("/"):
        from app.utils.public_urls import public_url_for

        url = public_url_for("auth.login")
        assert url.startswith("https://example.test")
        assert "/auth/login" in url


def test_public_url_for_falls_back_to_external_when_no_base(app):
    app.config["APP_BASE_URL"] = ""
    with app.test_request_context("/", base_url="http://localhost:5000/"):
        from app.utils.public_urls import public_url_for

        url = public_url_for("auth.login")
        assert "http" in url
        assert "/auth/login" in url
