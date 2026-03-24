from datetime import UTC, datetime

from app.constants import Roles
from app.extensions import db
from app.models.incident import Incident
from app.services.auth_service import auth_service


def _seed_hotspot_incident(
    *,
    user_id: int,
    ref: str,
    suburb: str,
    lat: float,
    lng: float,
    hotspot_excluded: bool = False,
):
    db.session.add(
        Incident(
            reported_by_id=user_id,
            title=f"Incident {ref}",
            description="Desc",
            category="Sanitation",
            suburb_or_ward=suburb,
            street_or_landmark="Main",
            location=f"Main, {suburb}",
            severity="low",
            status="reported",
            reference_code=ref,
            latitude=lat,
            longitude=lng,
            reported_at=datetime.now(UTC),
            hotspot_excluded=hotspot_excluded,
        )
    )


def test_admin_hotspot_api_requires_admin_role(app, client):
    with app.app_context():
        resident, _ = auth_service.register_user(
            name="Resident",
            email="heat-resident@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        _seed_hotspot_incident(
            user_id=resident.id,
            ref="HK-2026-03-820001",
            suburb="North",
            lat=-29.851,
            lng=31.021,
        )
        db.session.commit()

    client.post(
        "/auth/login",
        data={"email": "heat-resident@example.com", "password": "pass"},
        follow_redirects=True,
    )
    resp = client.get("/admin/api/admin/analytics/hotspots")
    assert resp.status_code in {302, 403}


def test_admin_hotspot_api_returns_points_and_areas(app, client):
    with app.app_context():
        admin, _ = auth_service.register_user(
            name="Admin",
            email="heat-admin-api@example.com",
            password="pass",
            role=Roles.ADMIN.value,
        )
        resident, _ = auth_service.register_user(
            name="Resident",
            email="heat-source@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        _seed_hotspot_incident(
            user_id=resident.id,
            ref="HK-2026-03-820010",
            suburb="Central",
            lat=-29.852,
            lng=31.025,
        )
        _seed_hotspot_incident(
            user_id=resident.id,
            ref="HK-2026-03-820011",
            suburb="Central",
            lat=-29.8523,
            lng=31.0246,
        )
        db.session.commit()

    client.post(
        "/auth/login",
        data={"email": "heat-admin-api@example.com", "password": "pass"},
        follow_redirects=True,
    )
    resp = client.get("/admin/api/admin/analytics/hotspots?days=7")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert "summary" in payload
    assert "points" in payload
    assert "areas" in payload
    assert payload["points"]
    assert payload["areas"]


def test_resident_heatmap_api_is_aggregated_and_thresholded(app, client):
    with app.app_context():
        resident, _ = auth_service.register_user(
            name="Resident",
            email="heat-resident-api@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        for idx in range(3):
            _seed_hotspot_incident(
                user_id=resident.id,
                ref=f"HK-2026-03-8300{idx}",
                suburb="Umbilo",
                lat=-29.90 + (idx * 0.001),
                lng=31.00 + (idx * 0.001),
            )
        _seed_hotspot_incident(
            user_id=resident.id,
            ref="HK-2026-03-83009",
            suburb="SparseArea",
            lat=-29.95,
            lng=31.10,
        )
        db.session.commit()

    client.post(
        "/auth/login",
        data={"email": "heat-resident-api@example.com", "password": "pass"},
        follow_redirects=True,
    )
    resp = client.get("/resident/api/resident/community-heatmap?days=7")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert "hotspots" in payload
    assert payload["hotspots"]
    first = payload["hotspots"][0]
    assert "area_name" in first
    assert "intensity" in first
    assert "count_band" in first
    assert "lat" in first and "lng" in first
    assert "exact_address" not in first
    assert all(item["area_name"] != "SparseArea" for item in payload["hotspots"])
