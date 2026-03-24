# Category Taxonomy Data Model and Migration Plan

## Current State

- Incidents store category as string and optional `category_id`.
- Guided booleans exist (`is_happening_now`, `is_anyone_in_danger`, `is_issue_still_present`).
- No generic structured JSON payload for category-specific details.

## Target State

- Add `incidents.dynamic_details` (JSON) for category-specific structured answers.
- Add `incidents.additional_notes` (text) for optional free text.
- Keep `incidents.description` as final readable summary.

## Migration

- Migration file: `migrations/versions/x4y5z6a7b8c9_incident_dynamic_details.py`
- Upgrade adds columns:
  - `additional_notes` TEXT NULL
  - `dynamic_details` JSON NULL
- Downgrade drops both columns.

## Backward Compatibility

- Existing incidents remain valid with `dynamic_details = NULL`.
- Admin templates render structured section only when details exist.
- Non-MVP categories continue using fallback schema and can submit without required dynamic fields.

## Rollback Plan

- Safe to rollback migration if no dependency is introduced on non-null values.
- Application logic must tolerate missing structured data at all times.

## Data Integrity Checks

- Validate JSON payload shape before persist via schema rules.
- Keep generated summary readable even with partial detail payloads.
- Ensure no submit path requires dynamic fields for fallback categories.
