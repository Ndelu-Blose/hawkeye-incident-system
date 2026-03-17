"""Analytics service: dashboard summary, hotspot data, authority performance."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.repositories.analytics_repo import AnalyticsRepository


class AnalyticsService:
    """Business logic for analytics and dashboard metrics."""

    def __init__(self, repo: AnalyticsRepository | None = None) -> None:
        self.repo = repo or AnalyticsRepository()

    def get_dashboard_summary(
        self,
        *,
        days: int = 7,
    ) -> dict:
        """Summary for admin analytics dashboard: totals, resolution times, categories, authorities."""
        since = datetime.now(UTC) - timedelta(days=days)

        total_this_week = self.repo.total_incidents_this_week(since)
        resolved_this_week = self.repo.resolved_this_week(since)
        avg_resolution = self.repo.avg_resolution_time_hours(since)

        categories = self.repo.avg_resolution_time_by_category(since)
        hotspots = self.repo.hotspots_by_suburb(since)
        authority_workload = self.repo.open_incidents_by_authority()
        dispatch_ack = self.repo.avg_dispatch_to_ack_time_by_authority(since)
        volume_by_day = self.repo.incident_volume_by_day(since)

        return {
            "total_this_week": total_this_week,
            "resolved_this_week": resolved_this_week,
            "avg_resolution_hours": avg_resolution,
            "categories": categories,
            "hotspots": hotspots,
            "authority_workload": authority_workload,
            "dispatch_ack_times": dispatch_ack,
            "volume_by_day": volume_by_day,
            "since": since,
            "days": days,
        }

    def get_hotspot_data(
        self,
        *,
        days: int = 30,
    ) -> list[dict]:
        """Hotspots by suburb for the given period."""
        since = datetime.now(UTC) - timedelta(days=days)
        return self.repo.hotspots_by_suburb(since)
