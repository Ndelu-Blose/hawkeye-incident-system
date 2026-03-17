## HawkEye v3.0 Progress Checklist

### Phase Overview

- [ ] **Phase 1 – Search, filters, reference codes, pagination**
- [ ] **Phase 2 – Location intelligence**
- [ ] **Phase 3 – Workflow hardening & timelines**
- [ ] **Phase 4 – Analytics & intelligence**
- [ ] **Phase 5 – Extended platform, notifications, SLAs, trust**

---

### Phase 1 – Search, Filters, and Scale

- [x] **Reference codes**
  - [x] Reference field on `Incident` (`reference_code`; renamed from `reference_no`)
  - [x] Format `HK-YYYY-MM-XXXXXX` generated on incident creation (PostgreSQL sequence; SQLite fallback in tests)
  - [x] DB-level uniqueness constraint and backfill: migration `i0j1k2l3m4n5` (sequence, rename, backfill NULLs, NOT NULL, UNIQUE)

- [x] **Resident Incident Explorer**
  - [x] Server-side search (`q`) on resident incidents
  - [x] Filters: status, category, date range, area
  - [x] Pagination for resident incidents (page object)
  - [x] Category filter on resident list (if required)
  - [x] Quick filters: My Open, My Resolved, This Month

- [x] **Admin Incident Console**
  - [x] Server-side search (`q`) on title, reference, id
  - [x] Filters: status, category, severity, authority, unassigned_only
  - [x] Filters: date range, area (suburb/ward)
  - [x] Pagination via `Page` dataclass
  - [x] Sort options: newest, oldest
  - [ ] Quick filters / presets (e.g. unassigned + high priority)

- [x] **Testing for Phase 1 (definition of done)**
  - [x] **Reference code behaviour**
    - [x] Unit test that `IncidentService.create_incident` always sets `reference_code` for new incidents.
    - [x] Unit test that `reference_code` matches `^HK-\d{4}-\d{2}-\d{6}$` (year, month, 6‑digit sequence).
    - [x] Unit test that creating multiple incidents in a single request cycle produces distinct `reference_code` values.
  - [x] **Resident incident explorer**
    - [x] Integration test: resident list respects `status`, `category_id`, `q`, `area`, `date_from`, `date_to` and combines them correctly.
    - [x] Integration test: resident list paginates correctly (page count, next/prev links preserve filters).
    - [x] Integration test: quick filters “My Open”, “My Resolved”, “This Month” apply the expected underlying filters.
  - [x] **Admin incident console**
    - [x] Integration test: admin list respects `status`, `category`, `severity`, `authority_id`, `unassigned_only`, `q`, `date_from`, `date_to`, `area`.
    - [x] Integration test: sort options / pagination verified together with filter tests.
    - [ ] (Optional, stretch) Preset/quick filter test once presets are implemented (e.g. “Unassigned + high severity”).
  - [x] **Performance / N+1**
    - [x] Automated smoke test that admin incident list does not perform an unreasonable number of queries when listing multiple incidents.

---

### Phase 2 – Location Intelligence

- [ ] **Schema**
  - [x] `latitude` / `longitude` columns on `Incident`
  - [x] `validated_address`, `suburb`, `ward`, `location_validated` on `Incident` (migration `k1l2m3n4o5p6`, model updated)

- [ ] **Location service**
  - [x] `services/location_service.py` (geocode + reverse geocode skeleton + `GeocodedLocation` dataclass)
  - [x] API key wiring via `GOOGLE_MAPS_API_KEY` env var (service reads from config when no explicit key passed)
  - [x] Incident creation path calls `location_service.geocode` (when configured) and populates `latitude`, `longitude`, `validated_address`, `suburb`, `ward`, `location_validated`

- [ ] **Resident UX**
  - [x] Places Autocomplete on report form (`street_or_landmark` with Google Places when `GOOGLE_MAPS_API_KEY` is set)
  - [x] Map pin-drop option on report form (draggable marker updates coordinates)
  - [x] Hidden fields (`latitude`, `longitude`) wired into incident creation payload
  - [x] **Use my current location** option with browser geolocation API
  - [x] **Current location UX enhancements** (tested)
    - [x] Loading states: "Detecting your current location...", "Getting address details..."
    - [x] Success message: "Location detected successfully. You can edit the address or drag the pin if needed."
    - [x] Helper text: "Auto-filled from your current location. You can edit these details or drag the pin."
    - [x] "Detect again" button for retry without switching options
    - [x] Inline help when permission denied (no blocking alerts)
    - [x] Improved autofill: suburb (sublocality/locality), street (route), nearest place (point_of_interest/establishment/neighborhood preferred over full address)
    - [x] All location fields remain editable
    - [x] Tested: full test suite passes; current location flow verified manually in browser

- [ ] **Backfill & filters**
  - [x] Geocoding backfill script for existing incidents (`scripts/geocode_backfill.py` using `location_service`)
  - [x] Suburb/ward filters using structured fields (admin area filter uses `suburb` / `ward` when present)
  - [x] Basic admin map view with markers (Google Maps on admin incident console when API key configured)

---

### Phase 3 – Workflow Hardening & Timelines

- [ ] **Lifecycle & history**
  - [x] Status enum and basic lifecycle implemented
  - [x] `IncidentUpdate` model for status/history entries
  - [x] Align statuses with v3 lifecycle (reported/screened/assigned/in_progress/resolved/closed/rejected) and migrate legacy `pending`/`verified`
  - [x] Enforce allowed transitions in a single service helper (`IncidentService.change_status`)

- [ ] **Dispatch & actions**
  - [x] `IncidentAssignment` model for authority assignments
  - [x] Extend to full `IncidentDispatch` shape (dispatch_method, ack fields, response_note)
  - [x] `DepartmentActionLog` model for department work and proof
  - [x] Every new `IncidentAssignment` creates an `incident_dispatches` row (auto-routing + admin confirm screening)
  - [x] `log_department_action(incident_id, authority_id, performed_by, action_type, note)` in IncidentService

- [ ] **Timelines & views**
  - [x] `assemble_timeline(incident_id)` that merges history, dispatches, and actions
  - [x] Resident incident detail timeline UI
  - [x] Admin incident detail timeline UI
  - [ ] Public area incident view (anonymised)

---

### Operational Backbone

- [ ] **Lifecycle & ownership**
  - [ ] All code paths that change `Incident.status` go through a single `IncidentService.change_status(...)` (or equivalent) method.
  - [ ] `IncidentService.change_status` validates transitions against the v3 lifecycle (`reported → screened → assigned → acknowledged → in_progress → resolved → closed` + `rejected`) and rejects invalid moves.
  - [ ] `IncidentService.change_status` always writes an `incident_events` row describing the change.
  - [ ] `IncidentService.change_status` writes an `audit_logs` row for sensitive transitions (manual close, rejection, overrides).
  - [ ] Ownership is represented only via `incident_ownership_history` with exactly one `is_current = true` row per incident.
  - [ ] No direct writes to `Incident.status` exist outside `IncidentService.change_status(...)` (enforced by code review and tests).

- [ ] **Dispatch & delivery**
  - [x] Every new `IncidentAssignment` (or routing event) creates an `incident_dispatches` row.
  - [x] `dispatch_method` (`internal_queue | email | sms | api`) and `delivery_status` (`pending | sent | delivered | failed`) are recorded for each dispatch.
  - [ ] Department queues are ultimately driven from `incident_dispatches` + `Incident.status`, not only `incident.current_authority_id`.
  - [ ] Acknowledgment from departments updates `incident_dispatches.ack_status`, `ack_user_id`, and `ack_at`.

- [ ] **Acknowledgment**
  - [ ] Department UI exposes an **Acknowledge incident** action that writes an `incident_events` entry and updates the relevant `incident_dispatches` row.
  - [ ] Incident timelines surface acknowledgment events (who acknowledged, when, via which channel).

- [ ] **Event ledger**
  - [ ] For incident creation, screening, routing, status changes, and evidence uploads, corresponding `incident_events` rows are written.
  - [ ] Resident and admin incident timelines are rendered from `incident_events` (no hard‑coded or fake history lines).

- [ ] **Audit**
  - [ ] Routing rule CRUD operations write `audit_logs` entries with `before_json` and `after_json` snapshots.
  - [ ] User role and activation/disablement changes write `audit_logs` rows.
  - [ ] Manual incident closes, reopens, and rejections write `audit_logs` entries with a non‑empty `reason`.
  - [ ] Tests assert that legal status transitions produce one `incident_events` row, the expected ownership change, and one `audit_logs` row; illegal transitions raise a domain error.

---

### Phase 4 – Analytics & Intelligence

- [ ] **Analytics plumbing**
  - [x] `analytics_repo.py` with volume, hotspot, performance queries (`incident_volume_by_day`, `avg_resolution_time_by_category`, `avg_dispatch_to_ack_time_by_authority`, `open_incidents_by_authority`, `hotspots_by_suburb`)
  - [x] `analytics_service.py` orchestration layer (`get_dashboard_summary`, `get_hotspot_data`)
  - [ ] `AnalyticsHotspotConfig` model + migration (future)

- [ ] **Admin analytics UI**
  - [x] `/admin/analytics` route
  - [x] Dashboard template: summary cards (total this week, resolved this week, avg resolution time), top categories, hotspots by suburb, authority workload, dispatch→ack times
  - [ ] Performance tests on seeded data (~10k incidents)

---

### Phase 5 – Extended Platform, Notifications, SLAs, Trust

- [ ] **Resident UX**
  - [ ] Satisfaction rating & feedback on resolved incidents
  - [x] Anonymous flag on `Incident` (schema)
  - [ ] Anonymous UX (hide identity from authorities/public)
  - [ ] Duplicate detection (nearby incidents) and supporting-evidence flow
  - [ ] Incident followers model and UI

- [ ] **SLA & escalation**
  - [ ] `sla_rules` and `escalation_rules` models
  - [ ] `sla_service.py` with SLA status calculations
  - [ ] Background jobs for SLA monitoring and escalation

- [ ] **Notification layer**
  - [x] Basic `NotificationLog` + email worker
  - [ ] New `Notification` + `NotificationPreference` schema
  - [ ] Centralised notification service (in-app, email, SMS)
  - [ ] In-app notification centre UI

- [ ] **Trust, public, and compliance**
  - [ ] `/public/status` public status page
  - [ ] Evidence hashing + chain-of-custody export
  - [ ] Resident data export endpoint and UI
  - [ ] Soft delete (`deleted_at`) + query filtering
  - [ ] Rate limiting on key endpoints
  - [ ] `category_knowledge_base` table and KB UI

