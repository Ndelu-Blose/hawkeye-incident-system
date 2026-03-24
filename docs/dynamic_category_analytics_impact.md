# Dynamic Category Analytics Impact

## Why This Matters

Structured incident details improve analytics quality and unlock per-category feature insights that free-text alone cannot provide.

## New Data Inputs

- `incidents.dynamic_details` JSON (category-specific fields)
- `incidents.additional_notes` text
- Existing category dimensions (`category`, `category_id`) remain unchanged

## Metric and Query Impact

- Resolution and volume metrics by category remain stable.
- New optional dimensions can be extracted from JSON:
  - Suspicious activity: `ongoing`, `vehicle_involved`
  - Theft: `forced_entry`, `suspect_seen`
  - Vandalism: `damage_severity`
  - Noise: `repeated_issue`, `still_active`

## Reporting Guidance

- Treat dynamic-detail dimensions as optional and sparse.
- Use `NULL`-safe aggregation so legacy incidents are included.
- Avoid making dashboard totals depend on JSON presence.

## Future Work

- Materialize high-value JSON fields into analytics tables.
- Add category-specific filters/badges in admin dashboards.
- Track schema-version metadata for long-term taxonomy evolution.
