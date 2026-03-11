from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.extensions import db
from app.models import Authority, IncidentCategory


def _normalize(text: str) -> str:
    return (text or "").lower()


FIRE_KEYWORDS: list[str] = ["fire", "smoke", "burning", "flames", "explosion"]
WATER_KEYWORDS: list[str] = ["leak", "burst pipe", "pipe burst", "water", "flood", "sewage"]
POLICE_KEYWORDS: list[str] = [
    "robbery",
    "theft",
    "suspicious",
    "assault",
    "fight",
    "gun",
    "armed",
    "break-in",
    "break in",
]
ELECTRICITY_KEYWORDS: list[str] = [
    "power outage",
    "no power",
    "electricity",
    "cable",
    "transformer",
    "sparks",
    "electrical box",
]
ROADS_KEYWORDS: list[str] = ["pothole", "road", "street", "damaged road", "sinkhole"]
WASTE_KEYWORDS: list[str] = ["garbage", "rubbish", "waste", "trash", "bin", "dumping"]
SECURITY_KEYWORDS: list[str] = ["trespassing", "security", "gang", "loitering", "threatening"]

URGENCY_KEYWORDS_HIGH: list[str] = [
    "urgent",
    "immediately",
    "dangerous",
    "injured",
    "bleeding",
    "attack",
    "armed",
    "explosion",
]


@dataclass
class ScreeningResult:
    system_category: IncidentCategory | None
    suggested_authority: Authority | None
    suggested_priority: str | None
    confidence: float
    flags: list[str]


class ScreeningService:
    """Rule-based screening of incident text to suggest category, department, and priority."""

    def __init__(self) -> None:
        self._category_cache: dict[str, IncidentCategory] = {}

    def _load_categories(self) -> Iterable[IncidentCategory]:
        return db.session.query(IncidentCategory).all()

    def _get_category_by_name(self, name: str) -> IncidentCategory | None:
        if not name:
            return None
        key = name.lower()
        if key in self._category_cache:
            return self._category_cache[key]
        cat = db.session.query(IncidentCategory).filter(IncidentCategory.name.ilike(name)).first()
        if cat is not None:
            self._category_cache[key] = cat
        return cat

    def screen_incident(
        self,
        *,
        title: str,
        description: str,
        resident_category: IncidentCategory | None,
    ) -> ScreeningResult:
        text = _normalize(f"{title} {description}")

        scores: dict[str, int] = {
            "fire": 0,
            "water": 0,
            "police": 0,
            "electricity": 0,
            "roads": 0,
            "waste": 0,
            "security": 0,
        }

        def add_score(label: str, keywords: list[str]) -> None:
            for kw in keywords:
                if kw in text:
                    scores[label] += 1

        add_score("fire", FIRE_KEYWORDS)
        add_score("water", WATER_KEYWORDS)
        add_score("police", POLICE_KEYWORDS)
        add_score("electricity", ELECTRICITY_KEYWORDS)
        add_score("roads", ROADS_KEYWORDS)
        add_score("waste", WASTE_KEYWORDS)
        add_score("security", SECURITY_KEYWORDS)

        # Boost matching resident category hint if provided.
        if resident_category is not None:
            name = resident_category.name.lower()
            if "fire" in name:
                scores["fire"] += 1
            if any(k in name for k in ("water", "sewer", "sewage")):
                scores["water"] += 1
            if any(k in name for k in ("crime", "safety", "security", "police")):
                scores["police"] += 1
                scores["security"] += 1
            if any(k in name for k in ("electric", "power")):
                scores["electricity"] += 1
            if any(k in name for k in ("road", "street")):
                scores["roads"] += 1
            if any(k in name for k in ("waste", "refuse", "garbage", "rubbish")):
                scores["waste"] += 1

        # Determine primary label.
        primary_label = max(scores, key=scores.get)
        primary_score = scores[primary_label]
        total = sum(scores.values()) or 1
        confidence = primary_score / total

        flags: list[str] = []
        # Multi-department candidate when there is a close second place.
        sorted_labels = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        if len(sorted_labels) > 1 and sorted_labels[1][1] > 0:
            second_score = sorted_labels[1][1]
            if second_score >= max(1, int(primary_score * 0.7)):
                flags.append("multi_department_candidate")

        # Urgency / suggested priority.
        suggested_priority: str | None = None
        if any(kw in text for kw in URGENCY_KEYWORDS_HIGH):
            suggested_priority = "critical"

        # Map label to a category name hint.
        label_to_category_name: dict[str, str] = {
            "fire": "Fire hazard",
            "water": "Water leak",
            "police": "Crime / safety",
            "electricity": "Electrical fault",
            "roads": "Road / infrastructure",
            "waste": "Waste / sanitation",
            "security": "Security issue",
        }
        system_category: IncidentCategory | None = None
        if primary_score > 0:
            cat_name = label_to_category_name.get(primary_label)
            if cat_name:
                system_category = self._get_category_by_name(cat_name)

        # Suggested authority currently relies on RoutingRule logic downstream,
        # so we only hint via category; routing_service will use category + location.
        suggested_authority: Authority | None = None

        return ScreeningResult(
            system_category=system_category,
            suggested_authority=suggested_authority,
            suggested_priority=suggested_priority,
            confidence=float(confidence),
            flags=flags,
        )


screening_service = ScreeningService()
