"""Seed default category->department routing rules.

This script is idempotent for global/default rules (location_id is NULL):
- Ensures every known category has one active default rule.
- Replaces existing default rule for a category with the configured department.
- Leaves location-specific rules untouched.

Run with:
    python scripts/seed_routing_rules.py
"""

from __future__ import annotations

import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import create_app
from app.extensions import db
from app.models.authority import Authority
from app.models.incident_category import IncidentCategory
from app.models.routing_rule import RoutingRule

# Category key -> authority slug
CATEGORY_TO_AUTHORITY_SLUG: dict[str, str] = {
    "water_leak": "water-and-sanitation",
    "blocked_drain": "water-and-sanitation",
    "crime": "saps",
    "suspicious_activity": "metro-police",
    "pothole": "roads-and-stormwater",
    "broken_streetlight": "electricity",
    "dumping": "waste-management",
    "vandalism": "public-safety",
}

FALLBACK_AUTHORITY_SLUG = "municipal-operations"


def _get_authorities_by_slug() -> dict[str, Authority]:
    authorities = Authority.query.filter(Authority.is_active.is_(True)).all()
    return {a.slug: a for a in authorities if a.slug}


def seed_default_routing_rules() -> tuple[int, int]:
    """Seed routing rules and return (updated_count, fallback_count)."""
    by_slug = _get_authorities_by_slug()
    fallback = by_slug.get(FALLBACK_AUTHORITY_SLUG)
    if fallback is None:
        raise RuntimeError(
            f"Fallback authority '{FALLBACK_AUTHORITY_SLUG}' not found. "
            "Run migrations/authority seed first."
        )

    updated = 0
    fallback_count = 0

    categories = IncidentCategory.query.order_by(IncidentCategory.name.asc()).all()
    for category in categories:
        target_slug = CATEGORY_TO_AUTHORITY_SLUG.get(category.name, FALLBACK_AUTHORITY_SLUG)
        authority = by_slug.get(target_slug, fallback)
        used_fallback = authority.slug != target_slug

        # Replace existing default (location-agnostic) rule for this category.
        RoutingRule.query.filter(
            RoutingRule.category_id == category.id,
            RoutingRule.location_id.is_(None),
        ).delete(synchronize_session=False)

        db.session.add(
            RoutingRule(
                category_id=category.id,
                location_id=None,
                authority_id=authority.id,
                is_active=True,
            )
        )
        updated += 1
        if used_fallback:
            fallback_count += 1

    db.session.commit()
    return updated, fallback_count


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        updated, fallback_used = seed_default_routing_rules()
        print(f"Seeded {updated} default routing rules.")
        print(f"Fallback used for {fallback_used} categories.")
