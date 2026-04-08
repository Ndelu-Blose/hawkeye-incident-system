from app.services import resend_email


def test_send_outbound_email_falls_back_to_smtp_when_resend_sdk_missing(app, monkeypatch):
    app.config["RESEND_API_KEY"] = "test-key"

    def fake_send_resend_email(*args, **kwargs):
        raise ModuleNotFoundError("No module named 'resend'")

    monkeypatch.setattr(resend_email, "send_resend_email", fake_send_resend_email)
    monkeypatch.setattr(resend_email.mail, "send", lambda _msg: None)

    with app.app_context():
        ok, err, provider = resend_email.send_outbound_email(
            app,
            to_email="resident@example.com",
            subject="subject",
            text_body="body",
            html_body="<p>body</p>",
        )

    assert ok is True
    assert err is None
    assert provider == "smtp"
