"""Transactional email: Resend (preferred) or SMTP via Flask-Mail (e.g. MailHog in Docker)."""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING

from flask_mail import Message

from app.extensions import mail

if TYPE_CHECKING:
    from flask import Flask


def send_resend_email(
    app: Flask,
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> tuple[bool, str | None]:
    """Send one email via Resend API only. Returns (success, error_detail_or_None)."""
    api_key = (app.config.get("RESEND_API_KEY") or "").strip()
    from_addr = (app.config.get("RESEND_FROM_EMAIL") or "").strip().strip('"').strip("'") or (
        (app.config.get("MAIL_DEFAULT_SENDER") or "").strip().strip('"').strip("'")
    )
    if not api_key:
        return False, "missing_resend_api_key"
    if not from_addr:
        return False, "missing_resend_from_email"

    try:
        import resend
    except ModuleNotFoundError as exc:
        # Some environments raise from nested imports; normalize for fallback logic.
        if "resend" in str(exc):
            return False, "resend_sdk_not_installed"
        return False, str(exc)

    resend.api_key = api_key
    params: dict[str, object] = {
        "from": from_addr,
        "to": [to_email],
        "subject": subject,
        "text": text_body,
    }
    if html_body:
        params["html"] = html_body

    try:
        resend.Emails.send(params)  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover - network/provider errors
        return False, str(exc)
    return True, None


def send_outbound_email(
    app: Flask,
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> tuple[bool, str | None, str]:
    """Send one email. Returns (success, error_message_or_None, provider_tag).

    Uses Resend when ``RESEND_API_KEY`` is set; otherwise Flask-Mail SMTP
    (``MAIL_SERVER`` / MailHog, etc.).
    """
    api_key = (app.config.get("RESEND_API_KEY") or "").strip()
    if api_key:
        try:
            ok, err = send_resend_email(
                app,
                to_email=to_email,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
            )
        except ModuleNotFoundError as exc:
            if "resend" in str(exc):
                ok, err = False, "resend_sdk_not_installed"
            else:
                ok, err = False, str(exc)
        except Exception as exc:
            ok, err = False, str(exc)
        if ok:
            return True, None, "resend"
        # In Docker/dev we may have RESEND_API_KEY set but no SDK installed.
        # Fall back to configured SMTP (MailHog) instead of raising a 500.
        if err not in ("resend_sdk_not_installed", "No module named 'resend'"):
            return False, err, "resend"

    try:
        msg = Message(subject=subject, recipients=[to_email.strip()], body=text_body)
        if html_body:
            msg.html = html_body
        mail.send(msg)
        return True, None, "smtp"
    except Exception as exc:
        return False, str(exc), "smtp"


def text_to_html_email(text: str) -> str:
    """Minimal HTML wrapper for plain-text notification bodies."""
    return (
        '<div style="font-family:system-ui,Segoe UI,sans-serif;font-size:15px;line-height:1.5">'
        f'<pre style="white-space:pre-wrap;margin:0">{escape(text)}</pre></div>'
    )
