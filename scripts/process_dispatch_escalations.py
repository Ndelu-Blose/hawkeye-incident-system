from __future__ import annotations

from app import create_app
from app.services.dispatch_service import dispatch_service


def main() -> None:
    app = create_app("production")
    with app.app_context():
        result = dispatch_service.process_auto_escalations(limit=200)
        app.logger.info(
            "Dispatch auto-escalation complete: processed=%s reminders_sent=%s failed=%s",
            result["processed"],
            result["reminders_sent"],
            result["failed"],
        )


if __name__ == "__main__":
    main()
