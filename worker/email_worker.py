from __future__ import annotations

import time
from collections.abc import Iterable

from flask import Flask
from flask_mail import Message

from app import create_app
from app.extensions import db, mail
from app.models.notification_log import NotificationLog
from app.repositories.notification_repo import NotificationRepository

POLL_INTERVAL_SECONDS = 5
BATCH_SIZE = 20


def _process_batch(
    app: Flask,
    repo: NotificationRepository,
) -> int:
    with app.app_context():
        queued: Iterable[NotificationLog] = repo.list_queued(limit=BATCH_SIZE)
        count = 0
        for notification in queued:
            try:
                if notification.recipient_email:
                    msg = Message(
                        subject=f"[Alertweb Solutions] {notification.type.replace('_', ' ').title()}",
                        recipients=[notification.recipient_email],
                        body=f"Notification for incident #{notification.incident_id}",
                    )
                    mail.send(msg)

                notification.status = "sent"
                db.session.add(notification)
                db.session.commit()
                count += 1
            except Exception as exc:  # pragma: no cover - best effort logging
                notification.status = "failed"
                notification.last_error = str(exc)
                db.session.add(notification)
                db.session.commit()

        return count


def run_worker() -> None:
    """Simple polling loop for processing queued notifications."""
    app = create_app()
    repo = NotificationRepository()

    while True:
        processed = _process_batch(app, repo)
        if processed == 0:
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_worker()
