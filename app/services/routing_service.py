from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from app.extensions import db
from app.models import (
    Authority,
    IncidentCategory,
    Location,
    RoutingRule,
)


@dataclass
class RoutingDecision:
    authority: Authority
    category: IncidentCategory
    location: Location | None
    priority: str | None
    sla_hours: int | None


class RoutingService:
    """Resolve which authority should receive an incident based on category and location."""

    def resolve(
        self,
        *,
        category: IncidentCategory,
        location: Location | None = None,
    ) -> RoutingDecision | None:
        """Return the best routing rule for the given category and location.

        Strategy:
        - Prefer active rules matching both category and specific location.
        - Fallback to active rules matching category only (location_id is NULL).
        - If nothing matches, return None.
        """
        base_query = select(RoutingRule).where(
            RoutingRule.is_active.is_(True),
            RoutingRule.category_id == category.id,
        )

        if location is not None:
            # Try location-specific rule first.
            stmt = base_query.where(RoutingRule.location_id == location.id)
            rule = db.session.execute(stmt).scalars().first()
            if rule is None:
                # Fallback to category-only rule.
                stmt = base_query.where(RoutingRule.location_id.is_(None))
                rule = db.session.execute(stmt).scalars().first()
        else:
            stmt = base_query.where(RoutingRule.location_id.is_(None))
            rule = db.session.execute(stmt).scalars().first()

        if rule is None:
            return None

        authority = rule.authority
        if authority is None or not authority.is_active:
            return None

        priority = rule.priority_override or category.default_priority
        sla_hours = rule.sla_hours_override or category.default_sla_hours

        return RoutingDecision(
            authority=authority,
            category=category,
            location=rule.location,
            priority=priority,
            sla_hours=sla_hours,
        )


routing_service = RoutingService()
