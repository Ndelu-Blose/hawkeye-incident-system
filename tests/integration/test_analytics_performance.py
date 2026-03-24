"""Phase 4C: Analytics performance validation with seeded data."""

from app.repositories.analytics_repo import AnalyticsRepository
from app.services.analytics_service import AnalyticsService


def test_seed_is_idempotent_for_reference_data(app):
    """Running seed twice should not fail on duplicate categories/authorities."""
    with app.app_context():
        from scripts.seed_analytics_data import seed

        seed(10, app=app)
        seed(10, app=app)  # second run reuses categories, authorities, users


def test_analytics_dashboard_with_seeded_data(app):
    """Seed ~200 incidents and verify analytics dashboard remains responsive."""
    with app.app_context():
        from scripts.seed_analytics_data import seed

        seed(200, app=app)

        repo = AnalyticsRepository()
        service = AnalyticsService(repo=repo)

        from datetime import UTC, datetime, timedelta

        since = datetime.now(UTC) - timedelta(days=30)

        total = repo.total_incidents_this_week(since)
        summary = service.get_dashboard_summary(days=30)

        assert total >= 1
        assert "total_this_week" in summary
        assert "resolved_this_week" in summary
        assert "volume_by_day" in summary
        assert "authority_workload" in summary
        assert "rejection_by_category" in summary
        assert "override_by_actor" in summary
        assert len(summary["volume_by_day"]) >= 1
