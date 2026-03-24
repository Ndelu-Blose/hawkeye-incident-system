"""Config-driven category schemas for guided incident reporting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FieldOption:
    value: str
    label: str


@dataclass(frozen=True)
class FieldSchema:
    key: str
    label: str
    field_type: str  # multiselect|select|boolean|text|number
    required: bool = False
    options: tuple[FieldOption, ...] = ()
    preserve_group: str | None = None
    show_when: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class CategorySchema:
    key: str
    label: str
    suggested_title: str
    helper_prompts: tuple[str, ...]
    safety_tip: str
    urgency_value: str
    fields: tuple[FieldSchema, ...]


def _opts(values: tuple[tuple[str, str], ...]) -> tuple[FieldOption, ...]:
    return tuple(FieldOption(value, label) for value, label in values)


MVP_SCHEMAS: dict[str, CategorySchema] = {
    "suspicious_activity": CategorySchema(
        key="suspicious_activity",
        label="Suspicious Activity",
        suggested_title="Suspicious Activity Reported",
        helper_prompts=(
            "Tell us what looked suspicious and where.",
            "Share people, vehicle, and direction details if visible.",
        ),
        safety_tip="Do not confront anyone. Keep a safe distance.",
        urgency_value="urgent_now",
        fields=(
            FieldSchema(
                key="activity_types",
                label="What did you notice?",
                field_type="multiselect",
                required=True,
                preserve_group="activity",
                options=_opts(
                    (
                        ("loitering", "Loitering"),
                        ("suspicious_vehicle", "Suspicious vehicle"),
                        ("trespassing", "Trespassing"),
                        ("tampering", "Tampering with property"),
                    )
                ),
            ),
            FieldSchema(
                key="people_count",
                label="How many people were involved?",
                field_type="number",
                preserve_group="people_count",
            ),
            FieldSchema(
                key="vehicle_involved",
                label="Vehicle involved?",
                field_type="boolean",
                preserve_group="vehicle_involved",
            ),
            FieldSchema(
                key="vehicle_description",
                label="Vehicle description",
                field_type="text",
                preserve_group="vehicle_description",
                show_when=(("vehicle_involved", "true"),),
            ),
            FieldSchema(
                key="ongoing",
                label="Is it happening now?",
                field_type="boolean",
                preserve_group="ongoing",
            ),
            FieldSchema(
                key="appearance",
                label="Appearance or clothing (optional)",
                field_type="text",
            ),
            FieldSchema(
                key="direction_of_movement",
                label="Direction of movement (optional)",
                field_type="text",
            ),
        ),
    ),
    "theft": CategorySchema(
        key="theft",
        label="Theft",
        suggested_title="Theft Reported",
        helper_prompts=(
            "Tell us what was taken and how the theft happened.",
            "Include suspect and forced-entry details if known.",
        ),
        safety_tip="Do not disturb evidence that may be needed for investigation.",
        urgency_value="urgent_now",
        fields=(
            FieldSchema(
                key="theft_type",
                label="Type of theft",
                field_type="select",
                required=True,
                preserve_group="incident_type",
                options=_opts(
                    (
                        ("personal_property", "Personal property"),
                        ("vehicle_related", "Vehicle-related theft"),
                        ("house_break_in", "House break-in"),
                        ("business_theft", "Business theft"),
                        ("other", "Other"),
                    )
                ),
            ),
            FieldSchema(
                key="item_stolen",
                label="Item(s) stolen",
                field_type="text",
                required=True,
                preserve_group="item_description",
            ),
            FieldSchema(
                key="estimated_value",
                label="Estimated value (optional)",
                field_type="text",
            ),
            FieldSchema(
                key="forced_entry",
                label="Was there forced entry?",
                field_type="boolean",
                preserve_group="forced_entry",
            ),
            FieldSchema(
                key="suspect_seen",
                label="Was a suspect seen?",
                field_type="boolean",
                preserve_group="suspect_seen",
            ),
            FieldSchema(
                key="discovery_time",
                label="When did you discover it?",
                field_type="text",
            ),
        ),
    ),
    "vandalism": CategorySchema(
        key="vandalism",
        label="Vandalism",
        suggested_title="Vandalism Reported",
        helper_prompts=(
            "Describe what was damaged and how severe it is.",
            "Tell us if damage is still happening or if suspects were seen.",
        ),
        safety_tip="Capture damage and nearby landmarks if safe.",
        urgency_value="soon",
        fields=(
            FieldSchema(
                key="property_type",
                label="What was damaged?",
                field_type="select",
                required=True,
                preserve_group="property_type",
                options=_opts(
                    (
                        ("public_property", "Public property"),
                        ("private_property", "Private property"),
                        ("vehicle", "Vehicle"),
                        ("utilities", "Utilities/infrastructure"),
                    )
                ),
            ),
            FieldSchema(
                key="damage_type",
                label="Type of damage",
                field_type="multiselect",
                required=True,
                preserve_group="damage_type",
                options=_opts(
                    (
                        ("graffiti", "Graffiti"),
                        ("broken_glass", "Broken glass"),
                        ("structural_damage", "Structural damage"),
                        ("tampering", "Tampering"),
                    )
                ),
            ),
            FieldSchema(
                key="damage_severity",
                label="Damage severity",
                field_type="select",
                preserve_group="damage_severity",
                options=_opts(
                    (
                        ("minor", "Minor"),
                        ("moderate", "Moderate"),
                        ("severe", "Severe"),
                    )
                ),
            ),
            FieldSchema(
                key="suspect_seen",
                label="Was a suspect seen?",
                field_type="boolean",
                preserve_group="suspect_seen",
            ),
            FieldSchema(
                key="still_happening",
                label="Is damage still happening now?",
                field_type="boolean",
                preserve_group="ongoing",
            ),
        ),
    ),
    "noise_complaint": CategorySchema(
        key="noise_complaint",
        label="Noise Complaint",
        suggested_title="Noise Complaint Reported",
        helper_prompts=(
            "Tell us the source and how long it has continued.",
            "Include whether this is a repeated issue.",
        ),
        safety_tip="Avoid confrontation. Report only what you can safely observe.",
        urgency_value="soon",
        fields=(
            FieldSchema(
                key="noise_source",
                label="Source of noise",
                field_type="select",
                required=True,
                preserve_group="noise_source",
                options=_opts(
                    (
                        ("music_party", "Music/party"),
                        ("construction", "Construction"),
                        ("vehicle", "Vehicle"),
                        ("animals", "Animals"),
                        ("other", "Other"),
                    )
                ),
            ),
            FieldSchema(
                key="duration",
                label="How long has it been going on?",
                field_type="text",
                preserve_group="duration",
            ),
            FieldSchema(
                key="time_of_day",
                label="Time of day",
                field_type="select",
                preserve_group="time_of_day",
                options=_opts(
                    (
                        ("morning", "Morning"),
                        ("afternoon", "Afternoon"),
                        ("evening", "Evening"),
                        ("night", "Night"),
                    )
                ),
            ),
            FieldSchema(
                key="repeated_issue",
                label="Is this a repeated issue?",
                field_type="boolean",
                preserve_group="repeated_issue",
            ),
            FieldSchema(
                key="still_active",
                label="Is the noise still active?",
                field_type="boolean",
                preserve_group="ongoing",
            ),
        ),
    ),
    "blocked_drain": CategorySchema(
        key="blocked_drain",
        label="Blocked Drain",
        suggested_title="Blocked Drain Reported",
        helper_prompts=(
            "Tell us what is happening at the drain.",
            "Include overflow and access impact if present.",
        ),
        safety_tip="Avoid direct contact with stagnant or dirty water.",
        urgency_value="soon",
        fields=(
            FieldSchema(
                key="drain_condition",
                label="Drain condition",
                field_type="select",
                preserve_group="drain_condition",
                options=_opts(
                    (
                        ("fully_blocked", "Fully blocked"),
                        ("slow_drainage", "Slow drainage"),
                        ("overflowing", "Overflowing"),
                    )
                ),
            ),
            FieldSchema(
                key="standing_water",
                label="Is standing water visible?",
                field_type="boolean",
                preserve_group="standing_water",
            ),
            FieldSchema(
                key="bad_smell",
                label="Is there a bad smell?",
                field_type="boolean",
                preserve_group="bad_smell",
            ),
            FieldSchema(
                key="affecting_access",
                label="Is access to homes/roads affected?",
                field_type="boolean",
                preserve_group="affecting_access",
            ),
        ),
    ),
    "water_leak": CategorySchema(
        key="water_leak",
        label="Water Leak",
        suggested_title="Water Leak Reported",
        helper_prompts=(
            "Tell us where the leak is and how severe it looks.",
            "Share if flooding is happening now.",
        ),
        safety_tip="Stay clear of fast-moving water and traffic areas.",
        urgency_value="urgent_now",
        fields=(
            FieldSchema(
                key="leak_source",
                label="Leak source",
                field_type="select",
                preserve_group="leak_source",
                options=_opts(
                    (
                        ("pipe", "Pipe"),
                        ("hydrant", "Hydrant"),
                        ("meter_connection", "Meter/connection"),
                        ("unknown", "Unknown"),
                    )
                ),
            ),
            FieldSchema(
                key="flooding",
                label="Is there visible flooding?",
                field_type="boolean",
                preserve_group="flooding",
            ),
            FieldSchema(
                key="ongoing",
                label="Is water still leaking now?",
                field_type="boolean",
                preserve_group="ongoing",
            ),
            FieldSchema(
                key="water_pressure_drop",
                label="Have nearby homes reported low pressure?",
                field_type="boolean",
                preserve_group="water_pressure_drop",
            ),
        ),
    ),
    "pothole": CategorySchema(
        key="pothole",
        label="Pothole",
        suggested_title="Pothole Reported",
        helper_prompts=(
            "Tell us the pothole size and exact road position.",
            "Mention whether cars/pedestrians are at risk.",
        ),
        safety_tip="Do not stand in active traffic while collecting evidence.",
        urgency_value="soon",
        fields=(
            FieldSchema(
                key="pothole_size",
                label="Pothole size",
                field_type="select",
                preserve_group="pothole_size",
                options=_opts(
                    (
                        ("small", "Small"),
                        ("medium", "Medium"),
                        ("large", "Large"),
                    )
                ),
            ),
            FieldSchema(
                key="traffic_risk",
                label="Is it dangerous to traffic?",
                field_type="boolean",
                preserve_group="traffic_risk",
            ),
            FieldSchema(
                key="pedestrian_risk",
                label="Is it dangerous to pedestrians?",
                field_type="boolean",
                preserve_group="pedestrian_risk",
            ),
            FieldSchema(
                key="near_junction_or_school",
                label="Is it near a junction or school route?",
                field_type="boolean",
                preserve_group="near_junction_or_school",
            ),
        ),
    ),
    "broken_streetlight": CategorySchema(
        key="broken_streetlight",
        label="Broken Streetlight",
        suggested_title="Streetlight not working",
        helper_prompts=(
            "Tell us if the light is off or flickering.",
            "Share if the area is very dark and unsafe.",
        ),
        safety_tip="Report from a safe location. Do not approach exposed wiring.",
        urgency_value="soon",
        fields=(
            FieldSchema(
                key="light_issue",
                label="Streetlight issue",
                field_type="select",
                preserve_group="light_issue",
                options=_opts(
                    (
                        ("completely_off", "Completely off"),
                        ("flickering", "Flickering"),
                        ("damaged_pole", "Damaged pole/light"),
                    )
                ),
            ),
            FieldSchema(
                key="area_darkness",
                label="Is the area very dark at night?",
                field_type="boolean",
                preserve_group="area_darkness",
            ),
            FieldSchema(
                key="safety_risk",
                label="Does this create a safety risk?",
                field_type="boolean",
                preserve_group="safety_risk",
            ),
        ),
    ),
    "dumping": CategorySchema(
        key="dumping",
        label="Illegal Dumping",
        suggested_title="Illegal dumping reported",
        helper_prompts=(
            "Describe what was dumped and approximate volume.",
            "Tell us if it is blocking access or causing hazards.",
        ),
        safety_tip="Do not handle dumped material directly.",
        urgency_value="soon",
        fields=(
            FieldSchema(
                key="dump_type",
                label="Type of dumped material",
                field_type="select",
                preserve_group="dump_type",
                options=_opts(
                    (
                        ("household_waste", "Household waste"),
                        ("construction_rubble", "Construction rubble"),
                        ("garden_waste", "Garden waste"),
                        ("mixed_unknown", "Mixed/unknown"),
                    )
                ),
            ),
            FieldSchema(
                key="dump_size",
                label="Approximate size",
                field_type="select",
                preserve_group="dump_size",
                options=_opts(
                    (
                        ("small", "Small"),
                        ("medium", "Medium"),
                        ("large", "Large"),
                    )
                ),
            ),
            FieldSchema(
                key="blocking_access",
                label="Is it blocking access?",
                field_type="boolean",
                preserve_group="blocking_access",
            ),
            FieldSchema(
                key="pest_or_health_risk",
                label="Is there a pest/health risk?",
                field_type="boolean",
                preserve_group="pest_or_health_risk",
            ),
        ),
    ),
}

FALLBACK_SCHEMA = CategorySchema(
    key="other",
    label="Other",
    suggested_title="Incident Reported",
    helper_prompts=("Describe what happened and where.",),
    safety_tip="Add details and evidence only if safe.",
    urgency_value="soon",
    fields=(),
)


LEGACY_TO_MVP = {
    "crime": "theft",
}


def normalize_category_key(value: str | None) -> str:
    if not value:
        return "other"
    key = value.strip().lower().replace(" ", "_")
    return LEGACY_TO_MVP.get(key, key)


def get_category_schema(category_key: str | None) -> CategorySchema:
    key = normalize_category_key(category_key)
    return MVP_SCHEMAS.get(key, FALLBACK_SCHEMA)


def serialize_schema(schema: CategorySchema) -> dict[str, Any]:
    return {
        "key": schema.key,
        "label": schema.label,
        "suggested_title": schema.suggested_title,
        "helper_prompts": list(schema.helper_prompts),
        "safety_tip": schema.safety_tip,
        "urgency_value": schema.urgency_value,
        "fields": [
            {
                "key": f.key,
                "label": f.label,
                "field_type": f.field_type,
                "required": f.required,
                "preserve_group": f.preserve_group,
                "show_when": [{"field": k, "equals": v} for k, v in f.show_when],
                "options": [{"value": o.value, "label": o.label} for o in f.options],
            }
            for f in schema.fields
        ],
    }


def validate_details(schema: CategorySchema, details: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in schema.fields:
        value = details.get(field.key)
        if field.required:
            if field.field_type == "multiselect":
                if not isinstance(value, list) or not value:
                    errors.append(f"{field.label} is required.")
            elif value in (None, "", []):
                errors.append(f"{field.label} is required.")
    return errors


def build_generated_description(
    schema: CategorySchema,
    details: dict[str, Any],
    additional_notes: str | None,
) -> str:
    notes = (additional_notes or "").strip()
    if schema.key == "suspicious_activity":
        activity = _join_list(details.get("activity_types"))
        people_count = details.get("people_count")
        ongoing = details.get("ongoing")
        vehicle = details.get("vehicle_description")
        parts = []
        if people_count:
            parts.append(f"{people_count} individual(s) were seen")
        else:
            parts.append("Suspicious activity was reported")
        if activity:
            parts.append(f"involving {activity}")
        if vehicle:
            parts.append(f"with a vehicle described as {vehicle}")
        if ongoing is True:
            parts.append("and the activity appears ongoing")
        sentence = " ".join(parts).strip()
        return _finalize(sentence, notes)
    if schema.key == "theft":
        theft_type = details.get("theft_type")
        item = (details.get("item_stolen") or "").strip()
        forced = details.get("forced_entry")
        suspect = details.get("suspect_seen")
        sentence = "A theft incident was reported"
        if theft_type:
            sentence += f" ({_option_label(schema, 'theft_type', theft_type)})"
        if item:
            sentence += f", involving stolen item(s): {item}"
        if forced is True:
            sentence += ", with signs of forced entry"
        if suspect is True:
            sentence += ", and a suspect was seen"
        return _finalize(sentence, notes)
    if schema.key == "vandalism":
        property_type = details.get("property_type")
        damage_type = _join_list(details.get("damage_type"))
        severity = details.get("damage_severity")
        sentence = "Vandalism was reported"
        if property_type:
            sentence += f" on {_option_label(schema, 'property_type', property_type).lower()}"
        if damage_type:
            sentence += f", including {damage_type}"
        if severity:
            sentence += f" (severity: {_option_label(schema, 'damage_severity', severity).lower()})"
        return _finalize(sentence, notes)
    if schema.key == "noise_complaint":
        source = details.get("noise_source")
        duration = (details.get("duration") or "").strip()
        repeated = details.get("repeated_issue")
        active = details.get("still_active")
        sentence = "A noise complaint was reported"
        if source:
            sentence += f" with source: {_option_label(schema, 'noise_source', source).lower()}"
        if duration:
            sentence += f", lasting {duration}"
        if repeated is True:
            sentence += ", and this appears to be a repeated issue"
        if active is True:
            sentence += ", and it is still active"
        return _finalize(sentence, notes)
    if schema.key == "blocked_drain":
        condition = details.get("drain_condition")
        standing_water = details.get("standing_water")
        affecting_access = details.get("affecting_access")
        sentence = "A blocked drain was reported"
        if condition:
            sentence += f" ({_option_label(schema, 'drain_condition', condition).lower()})"
        if standing_water is True:
            sentence += ", with standing water visible"
        if affecting_access is True:
            sentence += ", and access is affected"
        return _finalize(sentence, notes)
    if schema.key == "water_leak":
        source = details.get("leak_source")
        flooding = details.get("flooding")
        ongoing = details.get("ongoing")
        sentence = "A water leak was reported"
        if source:
            sentence += f" from {_option_label(schema, 'leak_source', source).lower()}"
        if flooding is True:
            sentence += ", with visible flooding"
        if ongoing is True:
            sentence += ", and the leak appears ongoing"
        return _finalize(sentence, notes)
    if schema.key == "pothole":
        size = details.get("pothole_size")
        traffic_risk = details.get("traffic_risk")
        sentence = "A pothole was reported"
        if size:
            sentence += f" ({_option_label(schema, 'pothole_size', size).lower()})"
        if traffic_risk is True:
            sentence += ", creating traffic risk"
        return _finalize(sentence, notes)
    if schema.key == "broken_streetlight":
        issue = details.get("light_issue")
        darkness = details.get("area_darkness")
        sentence = "A broken streetlight was reported"
        if issue:
            sentence += f" ({_option_label(schema, 'light_issue', issue).lower()})"
        if darkness is True:
            sentence += ", and the area is very dark at night"
        return _finalize(sentence, notes)
    if schema.key == "dumping":
        dump_type = details.get("dump_type")
        dump_size = details.get("dump_size")
        blocked = details.get("blocking_access")
        sentence = "Illegal dumping was reported"
        if dump_type:
            sentence += f" ({_option_label(schema, 'dump_type', dump_type).lower()})"
        if dump_size:
            sentence += (
                f", approximately {_option_label(schema, 'dump_size', dump_size).lower()} in size"
            )
        if blocked is True:
            sentence += ", and access is blocked"
        return _finalize(sentence, notes)
    return _finalize("An incident was reported.", notes)


def _join_list(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    items = [str(v).replace("_", " ").strip() for v in value if str(v).strip()]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" and {items[-1]}"


def _option_label(schema: CategorySchema, field_key: str, value: str) -> str:
    field = next((f for f in schema.fields if f.key == field_key), None)
    if not field:
        return value
    opt = next((o for o in field.options if o.value == value), None)
    return opt.label if opt else value


def _finalize(sentence: str, notes: str) -> str:
    text = sentence.strip().rstrip(".")
    if notes:
        return f"{text}. Additional notes: {notes}"
    return f"{text}."
