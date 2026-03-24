"""Category-based presets for the guided incident form: titles, urgency, prompts."""

from __future__ import annotations

from app.constants import UrgencyLevel
from app.services.incident_dynamic_schema import get_category_schema, normalize_category_key

# Preset key is category name (as stored in DB) or "other" for fallback.
# Keys must match IncidentCategory.name from seed / DB.
PRESETS: dict[str, dict] = {
    "suspicious_activity": {
        "suggested_title": "Suspicious activity reported",
        "default_urgency": UrgencyLevel.URGENT_NOW,
        "helper_prompts": [
            "What did you notice?",
            "Is the person or vehicle still there?",
            "How many people were involved?",
            "Any clothing, vehicle colour, or direction?",
        ],
        "ask_is_happening_now": True,
        "ask_is_anyone_in_danger": True,
        "ask_is_issue_still_present": True,
        "safety_tip": "Do not put yourself at risk to take a photo.",
    },
    "crime": {
        "suggested_title": "Criminal activity reported",
        "default_urgency": UrgencyLevel.URGENT_NOW,
        "helper_prompts": [
            "What happened?",
            "Is the person or vehicle still there?",
            "Any description or direction they went?",
        ],
        "ask_is_happening_now": True,
        "ask_is_anyone_in_danger": True,
        "ask_is_issue_still_present": False,
        "safety_tip": "Do not put yourself at risk to take a photo.",
    },
    "vandalism": {
        "suggested_title": "Vandalism or damage reported",
        "default_urgency": UrgencyLevel.NEEDS_ATTENTION_SOON,
        "helper_prompts": [
            "What was damaged?",
            "Where exactly is the damage?",
            "Is the issue still present?",
        ],
        "ask_is_happening_now": False,
        "ask_is_anyone_in_danger": False,
        "ask_is_issue_still_present": True,
        "safety_tip": "Try to capture both the damage and the surrounding area.",
    },
    "dumping": {
        "suggested_title": "Illegal dumping reported",
        "default_urgency": UrgencyLevel.NEEDS_ATTENTION_SOON,
        "helper_prompts": [
            "What was dumped?",
            "Rough size of the dump?",
            "Is it blocking access or attracting pests?",
            "Is it still there now?",
        ],
        "ask_is_happening_now": False,
        "ask_is_anyone_in_danger": False,
        "ask_is_issue_still_present": True,
        "safety_tip": "Try to capture both the pile and the surrounding area.",
    },
    "broken_streetlight": {
        "suggested_title": "Streetlight not working",
        "default_urgency": UrgencyLevel.NEEDS_ATTENTION_SOON,
        "helper_prompts": [
            "Is it completely off or flickering?",
            "How long has it been like this?",
            "Is the area very dark at night?",
        ],
        "ask_is_happening_now": False,
        "ask_is_anyone_in_danger": False,
        "ask_is_issue_still_present": True,
        "safety_tip": "Try to capture the streetlight and the area so we can locate it.",
    },
    "pothole": {
        "suggested_title": "Road hazard reported",
        "default_urgency": UrgencyLevel.NEEDS_ATTENTION_SOON,
        "helper_prompts": [
            "Is it small, medium, or large?",
            "Is it dangerous to cars or pedestrians?",
            "Is it near a junction, school, or taxi route?",
        ],
        "ask_is_happening_now": False,
        "ask_is_anyone_in_danger": False,
        "ask_is_issue_still_present": True,
        "safety_tip": "Try to capture both the hazard and the surrounding area.",
    },
    "water_leak": {
        "suggested_title": "Water leak or burst reported",
        "default_urgency": UrgencyLevel.URGENT_NOW,
        "helper_prompts": [
            "Where is the leak (road, pavement, property)?",
            "Is water flowing onto the road or causing flooding?",
            "Is it still leaking now?",
        ],
        "ask_is_happening_now": True,
        "ask_is_anyone_in_danger": False,
        "ask_is_issue_still_present": True,
        "safety_tip": "Try to capture the leak and the surrounding area.",
    },
    "blocked_drain": {
        "suggested_title": "Blocked drain reported",
        "default_urgency": UrgencyLevel.NEEDS_ATTENTION_SOON,
        "helper_prompts": [
            "What is blocking it (if visible)?",
            "Is water pooling or flooding?",
            "Is it still blocked now?",
        ],
        "ask_is_happening_now": False,
        "ask_is_anyone_in_danger": False,
        "ask_is_issue_still_present": True,
        "safety_tip": "Try to capture the drain and surrounding area.",
    },
    "other": {
        "suggested_title": "Incident reported",
        "default_urgency": UrgencyLevel.NEEDS_ATTENTION_SOON,
        "helper_prompts": [
            "What happened?",
            "Where exactly is it?",
            "Is it still happening or still there?",
        ],
        "ask_is_happening_now": True,
        "ask_is_anyone_in_danger": True,
        "ask_is_issue_still_present": True,
        "safety_tip": "Add at least one photo if it is safe to do so.",
    },
}


def get_preset_key(category: object) -> str:
    """Return the preset key for an IncidentCategory (use name) or 'other'."""
    if category is None:
        return "other"
    name = getattr(category, "name", None)
    if not name or not isinstance(name, str):
        return "other"
    key = normalize_category_key(name)
    return key if key in PRESETS else "other"


def get_preset(category: object) -> dict:
    """Return the preset dict for the given category (model or key string)."""
    if isinstance(category, str):
        key = normalize_category_key(category) if category else "other"
    else:
        key = get_preset_key(category)
    preset = PRESETS.get(key, PRESETS["other"]).copy()
    schema = get_category_schema(key)
    if schema.key != "other":
        preset["suggested_title"] = schema.suggested_title
        preset["helper_prompts"] = list(schema.helper_prompts)
        preset["safety_tip"] = schema.safety_tip
        urgency_map = {
            "urgent_now": UrgencyLevel.URGENT_NOW,
            "soon": UrgencyLevel.NEEDS_ATTENTION_SOON,
            "scheduled": UrgencyLevel.CAN_BE_SCHEDULED,
        }
        preset["default_urgency"] = urgency_map.get(
            schema.urgency_value, preset.get("default_urgency")
        )
    return preset


def urgency_to_severity(urgency: str | None) -> str:
    """Map resident-facing urgency to system severity for routing/SLA."""
    if not urgency:
        return "medium"
    u = urgency.strip().lower()
    if u in ("urgent_now", "urgent now"):
        return "high"
    if u in ("soon", "needs_attention_soon"):
        return "medium"
    if u in ("scheduled", "can_be_scheduled"):
        return "low"
    return "medium"
