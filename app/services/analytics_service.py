"""Analytics service: dashboard summary, hotspot data, authority performance."""

from __future__ import annotations

from collections import defaultdict
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
        rejection_by_category = self.repo.rejection_count_by_category(since)
        override_by_actor = self.repo.override_count_by_actor(since)

        return {
            "total_this_week": total_this_week,
            "resolved_this_week": resolved_this_week,
            "avg_resolution_hours": avg_resolution,
            "categories": categories,
            "hotspots": hotspots,
            "authority_workload": authority_workload,
            "dispatch_ack_times": dispatch_ack,
            "volume_by_day": volume_by_day,
            "rejection_by_category": rejection_by_category,
            "override_by_actor": override_by_actor,
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

    def get_admin_hotspot_map(
        self,
        *,
        days: int = 7,
        category: str | None = None,
        statuses: list[str] | None = None,
        authority_id: int | None = None,
    ) -> dict:
        """Admin hotspot payload with weighted point clusters and area totals."""
        since = datetime.now(UTC) - timedelta(days=days)
        incidents = self.repo.hotspot_incident_points(
            since=since,
            category=category,
            statuses=statuses,
            authority_id=authority_id,
        )
        points = self._cluster_points(incidents)
        areas = self._aggregate_areas(incidents)
        top_area = areas[0]["name"] if areas else None
        return {
            "summary": {
                "total_incidents": len(incidents),
                "top_area": top_area,
                "hotspot_count": len(points),
            },
            "points": points,
            "areas": areas[:10],
        }

    def get_resident_community_heatmap(
        self,
        *,
        days: int = 7,
        category: str | None = None,
        near_suburb: str | None = None,
        min_threshold: int = 3,
    ) -> dict:
        """Resident-safe hotspot payload with aggregation and thresholding."""
        since = datetime.now(UTC) - timedelta(days=days)
        incidents = self.repo.hotspot_incident_points(
            since=since,
            category=category,
            near_suburb=near_suburb,
        )
        areas = self._aggregate_areas(incidents)
        visible_areas = [area for area in areas if area["count"] >= min_threshold]
        max_count = max((area["count"] for area in visible_areas), default=1)
        hotspots = []
        for area in visible_areas:
            intensity = round(area["count"] / max_count, 2)
            hotspots.append(
                {
                    "area_name": area["name"],
                    "lat": round(area["lat"], 3),
                    "lng": round(area["lng"], 3),
                    "intensity": intensity,
                    "count_band": self._count_band(intensity),
                }
            )
        top_area = hotspots[0]["area_name"] if hotspots else None
        return {
            "summary": {
                "visible_areas": len(hotspots),
                "top_area": top_area,
            },
            "hotspots": hotspots[:20],
            "meta": {
                "minimum_threshold": min_threshold,
                "privacy_mode": "aggregated",
            },
        }

    def _cluster_points(self, incidents: list[dict]) -> list[dict]:
        clusters: dict[tuple[float, float], dict] = {}
        for row in incidents:
            lat = float(row["latitude"])
            lng = float(row["longitude"])
            key = (round(lat, 3), round(lng, 3))
            current = clusters.setdefault(
                key,
                {
                    "lat_total": 0.0,
                    "lng_total": 0.0,
                    "count": 0,
                    "weight": 0.0,
                },
            )
            current["lat_total"] += lat
            current["lng_total"] += lng
            current["count"] += 1
            current["weight"] += self._incident_weight(row)
        points = []
        for item in clusters.values():
            count = item["count"] or 1
            points.append(
                {
                    "lat": round(item["lat_total"] / count, 5),
                    "lng": round(item["lng_total"] / count, 5),
                    "weight": round(item["weight"], 2),
                    "count": item["count"],
                }
            )
        points.sort(key=lambda row: row["weight"], reverse=True)
        return points

    def _aggregate_areas(self, incidents: list[dict]) -> list[dict]:
        grouped: dict[str, dict] = defaultdict(
            lambda: {"count": 0, "lat_total": 0.0, "lng_total": 0.0}
        )
        for row in incidents:
            area_name = (
                row.get("suburb") or row.get("ward") or row.get("suburb_or_ward") or "Unknown"
            )
            grouped[area_name]["count"] += 1
            grouped[area_name]["lat_total"] += float(row["latitude"])
            grouped[area_name]["lng_total"] += float(row["longitude"])
        areas = []
        for name, item in grouped.items():
            count = item["count"] or 1
            areas.append(
                {
                    "name": name,
                    "count": item["count"],
                    "lat": item["lat_total"] / count,
                    "lng": item["lng_total"] / count,
                }
            )
        areas.sort(key=lambda row: row["count"], reverse=True)
        return areas

    @staticmethod
    def _incident_weight(row: dict) -> float:
        weight = 1.0
        if row.get("severity") in {"high", "critical"}:
            weight += 1.0
        if row.get("status") in {"reported", "screened", "assigned", "acknowledged", "in_progress"}:
            weight += 0.5
        created_at = row.get("reported_at") or row.get("created_at")
        if created_at is not None:
            if getattr(created_at, "tzinfo", None) is None:
                created_at = created_at.replace(tzinfo=UTC)
            age_hours = (datetime.now(UTC) - created_at).total_seconds() / 3600
            if age_hours <= 24:
                weight += 0.5
            elif age_hours <= 72:
                weight += 0.25
        return round(max(weight, 0.25), 2)

    @staticmethod
    def _count_band(intensity: float) -> str:
        if intensity >= 0.8:
            return "high"
        if intensity >= 0.45:
            return "medium"
        return "low"
