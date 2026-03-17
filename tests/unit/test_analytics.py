"""Unit tests for AnalyticsRepository and AnalyticsService (Phase 4)."""

from datetime import UTC, datetime, timedelta

from app.constants import IncidentStatus, Roles
from app.extensions import db
from app.models.authority import Authority
from app.models.incident import Incident
from app.repositories.analytics_repo import AnalyticsRepository
from app.services.analytics_service import AnalyticsService
from app.services.auth_service import auth_service


def test_analytics_repo_incident_volume_by_day(app):
    """incident_volume_by_day returns counts per day."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Res",
            email="vol@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        now = datetime.now(UTC)
        for i in range(3):
            incident = Incident(
                reported_by_id=user.id,
                title=f"Incident {i}",
                description="D",
                category="C",
                suburb_or_ward="S",
                street_or_landmark="St",
                location="St, S",
                severity="low",
                status=IncidentStatus.REPORTED.value,
                reference_code=f"HK-2026-03-{i:06d}",
                reported_at=now - timedelta(days=i),
            )
            db.session.add(incident)
        db.session.commit()

        repo = AnalyticsRepository()
        since = now - timedelta(days=5)
        rows = repo.incident_volume_by_day(since)
        assert len(rows) >= 1
        assert all("day" in r and "count" in r for r in rows)


def test_analytics_repo_hotspots_by_suburb(app):
    """hotspots_by_suburb returns counts per suburb."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Res",
            email="hot@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        now = datetime.now(UTC)
        for i, suburb in enumerate(["North", "North", "South"]):
            incident = Incident(
                reported_by_id=user.id,
                title="Incident",
                description="D",
                category="C",
                suburb_or_ward=suburb,
                street_or_landmark="St",
                location="St, " + suburb,
                severity="low",
                status=IncidentStatus.REPORTED.value,
                reference_code=f"HK-2026-03-{i + 100:06d}",
                reported_at=now,
            )
            db.session.add(incident)
        db.session.commit()

        repo = AnalyticsRepository()
        since = now - timedelta(days=1)
        rows = repo.hotspots_by_suburb(since)
        assert len(rows) >= 1
        north = next((r for r in rows if r["suburb_or_ward"] == "North"), None)
        assert north is not None
        assert north["count"] >= 2


def test_analytics_repo_open_incidents_by_authority(app):
    """open_incidents_by_authority returns workload per department."""
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Res",
            email="open@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        auth = Authority(name="Water Dept", is_active=True)
        db.session.add(auth)
        db.session.commit()

        incident = Incident(
            reported_by_id=user.id,
            title="Leak",
            description="D",
            category="C",
            suburb_or_ward="S",
            street_or_landmark="St",
            location="St, S",
            severity="low",
            status=IncidentStatus.IN_PROGRESS.value,
            reference_code="HK-2026-03-000001",
            current_authority_id=auth.id,
        )
        db.session.add(incident)
        db.session.commit()

        repo = AnalyticsRepository()
        rows = repo.open_incidents_by_authority()
        assert len(rows) >= 1
        water = next((r for r in rows if r["authority_name"] == "Water Dept"), None)
        assert water is not None
        assert water["open_count"] >= 1


def test_analytics_service_get_dashboard_summary(app):
    """get_dashboard_summary returns expected keys."""
    with app.app_context():
        service = AnalyticsService()
        summary = service.get_dashboard_summary(days=7)
        assert "total_this_week" in summary
        assert "resolved_this_week" in summary
        assert "avg_resolution_hours" in summary
        assert "categories" in summary
        assert "hotspots" in summary
        assert "authority_workload" in summary
        assert "dispatch_ack_times" in summary
        assert "volume_by_day" in summary


def test_admin_analytics_route_returns_200(app, client):
    """Admin /analytics returns 200 and expected labels."""
    with app.app_context():
        admin, _ = auth_service.register_user(
            name="Admin",
            email="analytics-admin@example.com",
            password="pass",
            role="admin",
        )

    client.post(
        "/auth/login",
        data={"email": "analytics-admin@example.com", "password": "pass"},
        follow_redirects=True,
    )
    resp = client.get("/admin/analytics")
    assert resp.status_code == 200
    assert b"Analytics" in resp.data
    assert b"Total this week" in resp.data or b"total" in resp.data.lower()
    assert b"Resolved this week" in resp.data or b"resolved" in resp.data.lower()
