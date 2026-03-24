# Heatmap / Hotspot Implementation Spec

## Objective

Add a role-aware hotspot map capability that supports:
- operational decision-making for admins,
- privacy-safe community awareness for residents.

## Scope

- In scope:
  - location-ready incident schema metadata,
  - hotspot aggregation service with role-specific output,
  - admin and resident heatmap API contracts,
  - UI map cards and filter controls,
  - privacy and access-control tests.
- Out of scope (this phase):
  - predictive hotspot forecasting,
  - automated hotspot alerts,
  - advanced geospatial clustering beyond practical bucket aggregation.

## Role Behavior Matrix

| Capability | Admin | Resident |
|---|---|---|
| Endpoint | `/admin/api/admin/analytics/hotspots` | `/resident/api/resident/community-heatmap` |
| Coordinate precision | weighted clustered points | aggregated centroid only |
| Incident-level details | allowed for operations | not exposed |
| Filters | days, category, status, authority | days, category, near_suburb |
| Privacy thresholding | not required | required (minimum count) |

## Data Model Changes

`Incident` fields used by hotspot analytics:
- `latitude`, `longitude`
- `location_precision`
- `geocoded_at`
- `geocode_source`
- `hotspot_excluded`

## API Contracts

### Admin

`GET /admin/api/admin/analytics/hotspots`

Query params:
- `days` (1..90)
- `category` (optional)
- `status` (comma-separated, optional)
- `authority_id` (optional)

Response shape:

```json
{
  "summary": {
    "total_incidents": 41,
    "top_area": "Durban Central",
    "hotspot_count": 6
  },
  "points": [
    { "lat": -29.8584, "lng": 31.0219, "weight": 3.5, "count": 3 }
  ],
  "areas": [
    { "name": "Durban Central", "count": 14, "lat": -29.858, "lng": 31.021 }
  ]
}
```

### Resident

`GET /resident/api/resident/community-heatmap`

Query params:
- `days` (1..90)
- `category` (optional)
- `near_suburb` (optional)

Response shape:

```json
{
  "summary": {
    "visible_areas": 5,
    "top_area": "Durban Central"
  },
  "hotspots": [
    {
      "area_name": "Durban Central",
      "lat": -29.858,
      "lng": 31.021,
      "intensity": 0.88,
      "count_band": "high"
    }
  ],
  "meta": {
    "minimum_threshold": 3,
    "privacy_mode": "aggregated"
  }
}
```

## Privacy Policy

- Resident endpoint never returns:
  - identity fields,
  - evidence references,
  - descriptions/notes,
  - raw incident coordinate feed.
- Resident hotspot rendering uses:
  - grouped area aggregation,
  - minimum-threshold display rules,
  - generalized centroid coordinates.

## UI Behavior

- Admin analytics page:
  - hotspot map card with filters,
  - area summary table,
  - no-data and API-key missing states.
- Resident dashboard:
  - community heatmap card,
  - simplified time window control,
  - explicit privacy explanatory copy,
  - no incident drilldown from map.

## Acceptance Criteria

- Server enforces role-based endpoint access.
- Admin endpoint supports filtering and weighted output.
- Resident endpoint provides only privacy-safe aggregation.
- Unit and integration tests validate:
  - filtering behavior,
  - thresholding behavior,
  - role access control,
  - resident payload privacy contract.
