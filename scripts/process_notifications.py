from __future__ import annotations

from app import create_app
from app.services.notification_service import notification_service


def main() -> None:
    app = create_app("production")
    with app.app_context():
        result = notification_service.process_queued(limit=200)
        app.logger.info(
            "Notification processing complete: processed=%s sent=%s failed=%s",
            result["processed"],
            result["sent"],
            result["failed"],
        )


if __name__ == "__main__":
    main()
