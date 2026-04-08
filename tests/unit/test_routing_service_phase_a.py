from __future__ import annotations

from datetime import datetime, timedelta

from app.constants import IncidentStatus, Roles
from app.extensions import db
from app.models import Authority, Incident, IncidentCategory, Location, RoutingRule
from app.services.auth_service import auth_service
from app.services.routing_service import routing_service


def _make_incident(
    app, *, user_id: int, category: str, category_id: int, location_id: int | None
) -> Incident:
    with app.app_context():
        return Incident(
            reported_by_id=user_id,
            title="T",
            description="D",
            category=category,
            suburb_or_ward="S",
            street_or_landmark="St",
            location="St, S",
            severity="low",
            status=IncidentStatus.REPORTED.value,
            reference_code=f"HK-2026-03-ROUTE-{category_id}",
            final_category_id=category_id,
            location_id=location_id,
        )


def test_resolve_best_route_exact_beats_parent(app):
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="route-exact@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )

        cat = IncidentCategory(name="water_leak", description="Water leak", is_active=True)
        a_exact = Authority(name="Exact Dept", is_active=True)
        a_parent = Authority(name="Parent Dept", is_active=True)
        a_global = Authority(name="Global Dept", is_active=True)
        db.session.add_all([cat, a_exact, a_parent, a_global])
        db.session.flush()

        loc_root = Location(
            location_type="municipality", municipality="M1", parent_location_id=None
        )
        loc_parent = Location(
            location_type="district",
            district="D1",
            parent_location_id=loc_root.id if loc_root.id else None,
        )
        db.session.add(loc_root)
        db.session.flush()
        loc_parent.parent_location_id = loc_root.id
        db.session.add(loc_parent)
        db.session.flush()

        loc_child = Location(
            location_type="ward",
            ward="W1",
            parent_location_id=loc_parent.id,
        )
        db.session.add(loc_child)
        db.session.commit()

        r_exact = RoutingRule(
            category_id=cat.id,
            authority_id=a_exact.id,
            location_id=loc_child.id,
            priority=1,
            is_active=True,
        )
        r_parent = RoutingRule(
            category_id=cat.id,
            authority_id=a_parent.id,
            location_id=loc_parent.id,
            priority=2,
            is_active=True,
        )
        r_global = RoutingRule(
            category_id=cat.id,
            authority_id=a_global.id,
            location_id=None,
            priority=10,
            is_active=True,
        )
        db.session.add_all([r_exact, r_parent, r_global])
        db.session.commit()

        incident = Incident(
            reported_by_id=user.id,
            title="Leak",
            description="D",
            category=cat.name,
            suburb_or_ward="S",
            street_or_landmark="St",
            location="St, S",
            severity="low",
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-ROUTE-1",
            final_category_id=cat.id,
            location_id=loc_child.id,
        )
        db.session.add(incident)
        db.session.commit()

        decision = routing_service.resolve_best_route(incident)
        assert decision.authority_id == a_exact.id
        assert decision.routing_rule_id == r_exact.id
        assert decision.matched_location_id == loc_child.id
        assert decision.confidence == "high"
        assert decision.requires_admin_review is False


def test_resolve_best_route_parent_beats_global(app):
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="route-parent@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        cat = IncidentCategory(name="water_leak", description="Water leak", is_active=True)
        a_parent = Authority(name="Parent Dept", is_active=True)
        a_global = Authority(name="Global Dept", is_active=True)
        db.session.add_all([cat, a_parent, a_global])
        db.session.flush()

        loc_root = Location(location_type="municipality", municipality="M1")
        db.session.add(loc_root)
        db.session.flush()
        loc_parent = Location(
            location_type="district", district="D1", parent_location_id=loc_root.id
        )
        db.session.add(loc_parent)
        db.session.flush()
        loc_child = Location(location_type="ward", ward="W1", parent_location_id=loc_parent.id)
        db.session.add(loc_child)
        db.session.commit()

        r_parent = RoutingRule(
            category_id=cat.id,
            authority_id=a_parent.id,
            location_id=loc_parent.id,
            priority=2,
            is_active=True,
        )
        r_global = RoutingRule(
            category_id=cat.id,
            authority_id=a_global.id,
            location_id=None,
            priority=10,
            is_active=True,
        )
        db.session.add_all([r_parent, r_global])
        db.session.commit()

        incident = Incident(
            reported_by_id=user.id,
            title="Leak",
            description="D",
            category=cat.name,
            suburb_or_ward="S",
            street_or_landmark="St",
            location="St, S",
            severity="low",
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-ROUTE-2",
            final_category_id=cat.id,
            location_id=loc_child.id,
        )
        db.session.add(incident)
        db.session.commit()

        decision = routing_service.resolve_best_route(incident)
        assert decision.authority_id == a_parent.id
        assert decision.routing_rule_id == r_parent.id
        assert decision.confidence == "medium"
        assert decision.requires_admin_review is True


def test_resolve_best_route_ignores_future_effective_rules(app):
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="route-future@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        cat = IncidentCategory(name="water_leak", description="Water leak", is_active=True)
        a_exact = Authority(name="Exact Dept", is_active=True)
        a_global = Authority(name="Global Dept", is_active=True)
        db.session.add_all([cat, a_exact, a_global])
        db.session.flush()

        loc_root = Location(location_type="municipality", municipality="M1")
        db.session.add(loc_root)
        db.session.flush()
        loc_child = Location(location_type="ward", ward="W1", parent_location_id=loc_root.id)
        db.session.add(loc_child)
        db.session.commit()

        future_from = datetime.now().replace(tzinfo=None) + timedelta(days=1)

        r_future_exact = RoutingRule(
            category_id=cat.id,
            authority_id=a_exact.id,
            location_id=loc_child.id,
            priority=1,
            effective_from=future_from,
            is_active=True,
        )
        r_global = RoutingRule(
            category_id=cat.id,
            authority_id=a_global.id,
            location_id=None,
            priority=10,
            is_active=True,
        )
        db.session.add_all([r_future_exact, r_global])
        db.session.commit()

        incident = Incident(
            reported_by_id=user.id,
            title="Leak",
            description="D",
            category=cat.name,
            suburb_or_ward="S",
            street_or_landmark="St",
            location="St, S",
            severity="low",
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-ROUTE-3",
            final_category_id=cat.id,
            location_id=loc_child.id,
        )
        db.session.add(incident)
        db.session.commit()

        decision = routing_service.resolve_best_route(incident)
        assert decision.authority_id == a_global.id
        assert decision.confidence == "low"
        assert decision.requires_admin_review is True


def test_resolve_best_route_category_precedence_uses_final_category(app):
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="route-cat@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        cat_final = IncidentCategory(name="final_cat", description="Final", is_active=True)
        cat_reported = IncidentCategory(name="reported_cat", description="Reported", is_active=True)
        a_final = Authority(name="Final Dept", is_active=True)
        a_reported = Authority(name="Reported Dept", is_active=True)
        db.session.add_all([cat_final, cat_reported, a_final, a_reported])
        db.session.flush()

        r_final = RoutingRule(
            category_id=cat_final.id,
            authority_id=a_final.id,
            location_id=None,
            priority=5,
            is_active=True,
        )
        r_reported = RoutingRule(
            category_id=cat_reported.id,
            authority_id=a_reported.id,
            location_id=None,
            priority=4,
            is_active=True,
        )
        db.session.add_all([r_final, r_reported])
        db.session.commit()

        # final_category_id should win even if reported_category_id is set.
        incident = Incident(
            reported_by_id=user.id,
            title="T",
            description="D",
            category=cat_reported.name,
            suburb_or_ward="S",
            street_or_landmark="St",
            location="St, S",
            severity="low",
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-ROUTE-4",
            final_category_id=cat_final.id,
            reported_category_id=cat_reported.id,
            location_id=None,
        )
        db.session.add(incident)
        db.session.commit()

        decision = routing_service.resolve_best_route(incident)
        assert decision.authority_id == a_final.id
        assert decision.matched_category_id == cat_final.id


def test_resolve_best_route_tie_breaks_by_smallest_rule_id(app):
    with app.app_context():
        user, _ = auth_service.register_user(
            name="Resident",
            email="route-tie@example.com",
            password="pass",
            role=Roles.RESIDENT.value,
        )
        cat = IncidentCategory(name="water_leak", description="Water leak", is_active=True)
        a1 = Authority(name="Dept 1", is_active=True)
        a2 = Authority(name="Dept 2", is_active=True)
        db.session.add_all([cat, a1, a2])
        db.session.flush()

        loc_root = Location(location_type="municipality", municipality="M1")
        db.session.add(loc_root)
        db.session.flush()
        loc_child = Location(location_type="ward", ward="W1", parent_location_id=loc_root.id)
        db.session.add(loc_child)
        db.session.commit()

        # Same priority and same specificity; smaller rule.id should win deterministically.
        r1 = RoutingRule(
            category_id=cat.id,
            authority_id=a1.id,
            location_id=loc_child.id,
            priority=1,
            is_active=True,
        )
        db.session.add(r1)
        db.session.flush()
        r2 = RoutingRule(
            category_id=cat.id,
            authority_id=a2.id,
            location_id=loc_child.id,
            priority=1,
            is_active=True,
        )
        db.session.add(r2)
        db.session.commit()

        incident = Incident(
            reported_by_id=user.id,
            title="Leak",
            description="D",
            category=cat.name,
            suburb_or_ward="S",
            street_or_landmark="St",
            location="St, S",
            severity="low",
            status=IncidentStatus.REPORTED.value,
            reference_code="HK-2026-03-ROUTE-5",
            final_category_id=cat.id,
            location_id=loc_child.id,
        )
        db.session.add(incident)
        db.session.commit()

        decision = routing_service.resolve_best_route(incident)
        assert decision.routing_rule_id == r1.id
        assert decision.authority_id == a1.id
