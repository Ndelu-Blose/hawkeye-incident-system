from __future__ import annotations

import time

from flask import Flask

from app import create_app
from app.services.notification_service import notification_service

POLL_INTERVAL_SECONDS = 5
BATCH_SIZE = 20


def _process_batch(app: Flask) -> int:
    with app.app_context():
        stats = notification_service.process_queued(limit=BATCH_SIZE)
        app.logger.info(
            "email_worker_batch: batch_size=%s processed=%s sent=%s failed=%s",
            BATCH_SIZE,
            stats.get("processed", 0),
            stats.get("sent", 0),
            stats.get("failed", 0),
        )
        return int(stats.get("processed", 0))


def run_worker() -> None:
    """Polling loop for queued notification emails (same pipeline as the web app)."""
    app = create_app()
    app.logger.info(
        "email_worker_started: poll_interval_seconds=%s batch_size=%s",
        POLL_INTERVAL_SECONDS,
        BATCH_SIZE,
    )

    while True:
        processed = _process_batch(app)
        if processed == 0:
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_worker()
