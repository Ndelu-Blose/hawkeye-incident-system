"""Flask CLI commands."""

from __future__ import annotations

import click
from flask import Flask


def register_cli(app: Flask) -> None:
    @app.cli.command("email-test")
    @click.argument("to_email")
    def email_test(to_email: str) -> None:
        """Send a test email via Resend (if RESEND_API_KEY is set) or SMTP (Flask-Mail)."""
        from app.services.resend_email import send_outbound_email

        ok, err, provider = send_outbound_email(
            app,
            to_email=to_email.strip(),
            subject="Alertweb Solutions — email test",
            text_body=(
                "This is a test message from Alertweb Solutions.\n\n"
                "If you received it, outbound email is configured correctly."
            ),
            html_body=(
                "<p>This is a test message from <strong>Alertweb Solutions</strong>.</p>"
                "<p>If you received it, outbound email is configured correctly.</p>"
            ),
        )
        if ok:
            click.echo(f"Sent successfully via {provider}.")
        else:
            click.echo(f"Failed: {err}", err=True)
            raise SystemExit(1)
