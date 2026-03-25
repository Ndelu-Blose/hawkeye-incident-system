from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select

from app.constants import IncidentEventType
from app.extensions import db
from app.models import (
    Authority,
    IncidentCategory,
    IncidentEvent,
    Location,
    ResidentProfile,
    RoutingRule,
)
from app.models.incident import Incident


@dataclass
class LegacyRoutingDecision:
    authority: Authority
    category: IncidentCategory
    location: Location | None
    priority: str | None
    sla_hours: int | None


@dataclass
class RoutingDecision:
    authority_id: int | None
    routing_rule_id: int | None
    matched_location_id: int | None
    matched_category_id: int | None
    priority: int | None
    score: int | None
    reason: str
    requires_admin_review: bool
    confidence: str


class RoutingService:
    """Phase-A routing engine: resolve best authority suggestion only."""

    def resolve(
        self,
        *,
        category: IncidentCategory,
        location: Location | None = None,
    ) -> LegacyRoutingDecision | None:
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

        return LegacyRoutingDecision(
            authority=authority,
            category=category,
            location=rule.location,
            priority=priority,
            sla_hours=sla_hours,
        )

    @staticmethod
    def _normalize_category_token(value: str | None) -> str:
        if not value:
            return ""
        return value.strip().lower().replace("-", "_").replace(" ", "_")

    def resolve_category_id(self, incident: Incident) -> tuple[int | None, IncidentCategory | None]:
        """Determine routing category id using the Phase-A precedence contract."""
        for candidate_attr in (
            "final_category_id",
            "reported_category_id",
            "system_category_id",
            "category_id",
        ):
            candidate = getattr(incident, candidate_attr, None)
            if candidate:
                category = db.session.get(IncidentCategory, candidate)
                if category is not None and getattr(category, "is_active", True):
                    return category.id, category

        token = self._normalize_category_token(getattr(incident, "category", None))
        if not token:
            return None, None

        categories = (
            db.session.query(IncidentCategory).filter(IncidentCategory.is_active.is_(True)).all()
        )
        for category in categories:
            if self._normalize_category_token(category.name) == token:
                return category.id, category
        return None, None

    def build_location_chain(self, location_id: int | None) -> list[int]:
        """Build ancestor chain from most-specific to least-specific (self first)."""
        if location_id is None:
            return []

        chain: list[int] = []
        seen: set[int] = set()
        current = location_id
        while current is not None and current not in seen:
            seen.add(current)
            chain.append(current)
            location = db.session.get(Location, current)
            if location is None:
                break
            current = location.parent_location_id
        return chain

    def _resolve_location_starting_id(self, incident: Incident) -> int | None:
        """Best-effort starting point when incident.location_id is missing."""
        if incident.location_id:
            return incident.location_id

        profile = None
        if incident.resident_profile_id:
            profile = db.session.get(ResidentProfile, incident.resident_profile_id)
        if profile is not None:
            # Prefer the most-specific known level available.
            return profile.ward_id or profile.district_id or profile.municipality_id

        # Fall back to text fields (non-authoritative but deterministic).
        ward = getattr(incident, "ward", None) or getattr(incident, "suburb_or_ward", None)
        if ward:
            loc = db.session.execute(
                select(Location.id)
                .where(or_(Location.ward == ward, Location.suburb == ward))
                .limit(1)
            ).scalar_one_or_none()
            return int(loc) if loc is not None else None
        return None

    def resolve_best_route(self, incident: Incident) -> RoutingDecision:
        """
        Compute the best routing rule/authority suggestion without mutating incident ownership.
        """
        now = datetime.now(UTC)
        now_naive = now.replace(tzinfo=None)

        category_id, category = self.resolve_category_id(incident)
        if category_id is None or category is None:
            return RoutingDecision(
                authority_id=None,
                routing_rule_id=None,
                matched_location_id=None,
                matched_category_id=None,
                priority=None,
                score=None,
                reason="No routing category available.",
                requires_admin_review=True,
                confidence="none",
            )

        starting_location_id = self._resolve_location_starting_id(incident)
        location_chain = self.build_location_chain(starting_location_id)

        candidate_rules = self.get_candidate_rules(
            category_id=category_id, location_chain=location_chain, now_naive=now_naive
        )
        scored: list[tuple[int, RoutingRule, int | None, str]] = []
        for rule in candidate_rules:
            score, matched_location_id, confidence, reason = self.score_rule(
                rule, location_chain=location_chain
            )
            if score is None:
                continue
            scored.append((score, rule, matched_location_id, confidence))

        if not scored:
            return RoutingDecision(
                authority_id=None,
                routing_rule_id=None,
                matched_location_id=None,
                matched_category_id=category_id,
                priority=None,
                score=None,
                reason="No active routing rule matched this incident.",
                requires_admin_review=True,
                confidence="none",
            )

        # Deterministic tie-breaker: higher score wins; if still tied, smaller `rule.id` wins.
        best_score, best_rule, matched_location_id, confidence = sorted(
            scored,
            key=lambda t: (t[0], -t[1].id),
            reverse=True,
        )[0]

        requires_admin_review = confidence != "high"

        # Provide actionable, deterministic explanation.
        if best_rule.location_id is None:
            reason = (
                "Matched category-wide fallback routing rule (no specific location rule found)."
            )
        else:
            idx = (
                location_chain.index(best_rule.location_id)
                if best_rule.location_id in location_chain
                else 0
            )
            if idx == 0:
                reason = "Matched exact location routing rule."
            else:
                reason = f"Matched parent location routing rule (ancestor depth={idx})."

        return RoutingDecision(
            authority_id=best_rule.authority_id,
            routing_rule_id=best_rule.id,
            matched_location_id=matched_location_id,
            matched_category_id=category_id,
            priority=int(best_rule.priority) if best_rule.priority is not None else None,
            score=best_score,
            reason=reason,
            requires_admin_review=requires_admin_review,
            confidence=confidence,
        )

    def get_candidate_rules(
        self,
        *,
        category_id: int,
        location_chain: list[int],
        now_naive: datetime,
    ) -> list[RoutingRule]:
        """Fetch active rules that could match category and location scope."""
        q = select(RoutingRule).where(
            RoutingRule.is_active.is_(True),
            RoutingRule.category_id == category_id,
            or_(RoutingRule.effective_from.is_(None), RoutingRule.effective_from <= now_naive),
            or_(RoutingRule.effective_to.is_(None), RoutingRule.effective_to >= now_naive),
        )
        if location_chain:
            q = q.where(
                or_(RoutingRule.location_id.is_(None), RoutingRule.location_id.in_(location_chain))
            )
        else:
            q = q.where(RoutingRule.location_id.is_(None))
        return list(db.session.execute(q).scalars().all())

    def score_rule(
        self,
        rule: RoutingRule,
        *,
        location_chain: list[int],
    ) -> tuple[int | None, int | None, str, str]:
        """
        Score a candidate routing rule. Higher score is better.
        Confidence is derived from location specificity.
        """
        if rule.authority is None or not rule.authority.is_active:
            return None, None, "none", "Authority inactive."

        if rule.location_id is None:
            priority = int(rule.priority) if rule.priority is not None else 100
            score = 1000 - (priority * 10)
            return score, None, "low", "Matched global category fallback."

        if rule.location_id not in location_chain:
            return None, None, "none", "Location not in ancestor chain."

        depth = location_chain.index(rule.location_id)
        priority = int(rule.priority) if rule.priority is not None else 100

        if depth == 0:
            # Exact match.
            score = 3000 - (priority * 10)
            return score, rule.location_id, "high", "Exact location match."

        # Parent/ancestor match.
        score = 2000 - (priority * 10) - (depth * 100)
        return score, rule.location_id, "medium", "Parent location match."

    def apply_route_suggestion(
        self,
        incident: Incident,
        decision: RoutingDecision,
    ) -> None:
        """
        Mutate only suggestion-related fields and write a routing event (no ownership/dispatch yet).
        """
        if decision.authority_id is None:
            incident.suggested_authority_id = None
            incident.requires_admin_review = True
            event_type = IncidentEventType.ROUTING_FAILED.value
            metadata: dict[str, Any] = {
                "category_id": decision.matched_category_id,
                "location_id": getattr(incident, "location_id", None),
            }
            note = decision.reason
            authority_id = None
        else:
            incident.suggested_authority_id = decision.authority_id
            incident.requires_admin_review = (
                bool(incident.requires_admin_review) or decision.requires_admin_review
            )
            event_type = IncidentEventType.ROUTE_SUGGESTED.value
            metadata = {
                "routing_rule_id": decision.routing_rule_id,
                "matched_location_id": decision.matched_location_id,
                "matched_category_id": decision.matched_category_id,
                "confidence": decision.confidence,
                "priority": decision.priority,
                "score": decision.score,
            }
            note = decision.reason
            authority_id = decision.authority_id

        event = IncidentEvent(
            incident_id=incident.id,
            event_type=event_type,
            actor_user_id=None,
            actor_role="system",
            authority_id=authority_id,
            dispatch_id=None,
            assignment_id=None,
            from_status=None,
            to_status=None,
            reason=note,
            note=note,
            metadata_json=metadata,
        )
        db.session.add(event)
        db.session.flush()


routing_service = RoutingService()
