from __future__ import annotations

from app import create_app
from app.services.notification_service import notification_service


def main() -> None:
    app = create_app("production")
    with app.app_context():
        retried = notification_service.retry_failed(limit=500)
        app.logger.info("Notification retry complete: retried=%s", retried)


if __name__ == "__main__":
    main()
