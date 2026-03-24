# Phase 4 — Cleanup Pass & Analytics Migration Checklist

**Version 2.0 | March 2026**

---

## Backbone Milestone Completion Statement

The Operational Backbone milestone is complete. HawkEye now enforces lifecycle transitions through a canonical status engine, records domain activity in an event ledger, tracks ownership history, audits sensitive actions, supports dispatch acknowledgment, renders timelines from operational events, and protects these guarantees with contract tests.

This means Phase 4 can now build on trusted workflow data rather than mixed or loosely inferred history.

---

## Purpose of This Cleanup Pass

Before expanding analytics and intelligence features, HawkEye needs a short cleanup pass to identify and contain remaining transitional dependencies. The goal is to ensure that Phase 4 analytics are based on the new operational backbone, not partially on legacy paths.

This cleanup pass focuses on four areas:

- remaining legacy dependencies
- transitional `IncidentUpdate` usage
- analytics that should become event-backed
- queue logic still partially depending on `current_authority_id`

---

## 1. Legacy Dependency Inventory

### Objective

Identify all areas of the codebase that still rely on pre-backbone workflow patterns or snapshot-based assumptions instead of the new event-led operational model.

### Inventory Table

| Area | File/Module | Legacy Dependency | Current Use | Target State | Priority |
|------|-------------|-------------------|-------------|--------------|----------|
| Timeline fallback | `incident_service._timeline_from_legacy` | IncidentUpdate | Fallback when no incident_events | Keep until backfill | Low |
| History display | `get_incident_with_history`, templates | IncidentUpdate | Updates list in detail views | Consider timeline-only | Medium |
| Status writes | `incident_service` | Dual-write IncidentUpdate | Compatibility | Retire after backfill | Low |
| Completed queue | `incident_repo.list_for_authority` | ~~current_authority_id~~ | ✓ Uses ownership_history | Done | — |
| Open workload | `analytics_repo.open_incidents_by_authority` | ~~current_authority_id~~ | ✓ Uses ownership_history | Done | — |
| Dashboard overview | `dashboard_service.get_overview_by_authority` | current_authority_id | Authority workload counts | ownership_history | Medium |
| Admin list filter | `incident_repo.list_for_admin` | current_authority_id | Filter by authority | Acceptable (convenience) | Low |
| Unassigned count | `incident_repo.count_unassigned` | current_authority_id | Unassigned count | Acceptable | Low |

### v3 Lifecycle (Reference)

- `reported` → `screened` → `assigned` → `acknowledged` → `in_progress` → `resolved` → `closed`
- `rejected` (from reported, screened, assigned, acknowledged, in_progress)

---

## 2. IncidentUpdate Retirement Watchlist

### Objective

Treat `IncidentUpdate` as transitional only and track where it still exists so it can be retired in a controlled way.

### Current Role

`IncidentUpdate` should now be considered a legacy compatibility mechanism, mainly for:

- older incidents with no `incident_events`
- temporary timeline fallback during migration

### Watchlist

| Usage Area | Why It Still Exists | Safe to Migrate Now? | Notes |
|------------|---------------------|----------------------|-------|
| `change_status` | Dual-write for compatibility | No | Keep until timeline fallback removed |
| `create_incident` | Created, routing, screening, evidence updates | No | incident_events has incident_created |
| `edit_incident`, `attach_media` | No event types yet | Partial | Could add incident_edited, evidence_uploaded |
| `get_incident_with_history` | Returns updates for templates | Yes | Switch to timeline or event-derived |
| `_timeline_from_legacy` | Legacy incidents without events | No | Required for old data |
| Templates (admin/resident/authority detail) | Display updates section | Yes | May be redundant with timeline |

### Target State

- `incident_events` is the primary source for workflow history
- `IncidentUpdate` is fallback-only
- no new product features should depend on `IncidentUpdate`
- retirement path documented before removal

---

## 3. Event-Backed Analytics Migration Map

### Primary Backbone Sources

- `incident_events`
- `incident_dispatches`
- `incident_ownership_history`

### Migration Map

| Metric | Current Source | Target Source | Status |
|--------|----------------|---------------|--------|
| Incident volume by day | ~~Incident.reported_at~~ | `incident_events` (incident_created) | ✓ Done |
| Average resolution time | ~~Incident.resolved_at~~ | `incident_events` (created → resolved) | ✓ Done |
| Dispatch-to-ack time | `incident_dispatches` | Already event-backed | ✓ |
| Authority workload (open) | ~~current_authority_id~~ | `IncidentOwnershipHistory` (is_current) | ✓ Done |
| Hotspots by suburb | `Incident.suburb_or_ward` | No change needed | ✓ |
| Rejection patterns | — | `incident_events` + `rejection_count_by_category` | ✓ Done |
| Override patterns | — | `audit_logs` + `override_count_by_actor` | ✓ Done |

---

## 4. Queue Logic Cleanup Notes

### Completed Queue Policy (Documented)

**Policy: Option A — "Participated"**

The completed queue uses `exists(IncidentOwnershipHistory)` where the authority has **any** ownership row for the incident. This means:

- If incident was assigned to A, reassigned to B, resolved by B → **both A and B** see it in completed
- Semantics: "incidents this authority participated in that are now resolved/closed"

**Alternative (not implemented):** Option B — "Final owner" would show only the authority that owned at resolution. Current choice (Option A) is safer and preserves historical workload visibility.

### Queue Status

| Queue | Current Logic | Desired Logic | Status |
|-------|--------------|---------------|--------|
| Incoming | Dispatch + ownership + assigned | — | ✓ Aligned |
| Acknowledged | Ownership + acknowledged | — | ✓ Aligned |
| In progress | Ownership + in_progress | — | ✓ Aligned |
| Completed | ownership_history (any participation) | Documented above | ✓ Aligned |

### Remaining

- `current_authority_id` remains a convenience/cache field, not sole source of queue truth
- `dashboard_service.get_overview_by_authority` still uses current_authority_id; could migrate to ownership for consistency

---

## 5. Phase 4 Execution Order

### Phase 4A — Cleanup and Migration Map ✓

Deliverables:

- [x] Legacy dependency checklist
- [x] IncidentUpdate watchlist
- [x] Analytics migration map
- [x] Queue cleanup notes
- [x] Completed queue policy documented

### Phase 4B — Analytics Query Hardening

Deliverables:

- [x] open_incidents_by_authority → ownership_history
- [x] completed queue → ownership_history
- [x] Resolution time → incident_events
- [x] Volume by day → incident_events
- [x] total_this_week, resolved_this_week → incident_events
- [x] Rejection/override pattern queries
- [ ] Validation of metric definitions

### Phase 4B — Analytics Migrations (Event-Backed)

| Metric | Source |
|--------|--------|
| incident_volume_by_day | `incident_events` (incident_created) |
| total_incidents_this_week | `incident_events` (incident_created) |
| resolved_this_week | `incident_events` (incident_resolved) |
| avg_resolution_time_hours | `incident_events` (created → resolved) |
| avg_resolution_time_by_category | `incident_events` (created → resolved) |
| rejection_count_by_category | `incident_events` (incident_rejected) |
| override_count_by_actor | `audit_logs` (incident_status_override) |

### Phase 4C — Performance Validation

Deliverables:

- Query checks on seeded / larger datasets
- Dashboard performance review
- Heavy query and aggregation review

### Phase 4D — Admin Analytics UI Refinement

Deliverables:

- Summary cards aligned to trusted metrics
- Charts sourced from hardened queries
- Drill-down filters
- Structured location filters

---

## 6. Risks and Migration Notes

### Risk 1: Mixed truth in analytics

If some dashboards read from `incident_events` while others still depend on legacy `IncidentUpdate` or snapshot-only logic, users may see conflicting numbers.

**Mitigation:** Document source of truth per metric; migrate high-visibility metrics first.

### Risk 2: Legacy fallback becoming permanent

If fallback paths are never reviewed, `IncidentUpdate` may remain in production longer than intended.

**Mitigation:** Maintain visible retirement watchlist; avoid adding new features on legacy history.

### Risk 3: Queue/report mismatch

If operational queues use dispatch/ownership logic but analytics still use `current_authority_id`, workload reporting may be misleading.

**Mitigation:** ✓ Aligned for open workload and completed queue. Dashboard overview_by_authority remains.

### Risk 4: Performance regressions

Event-backed analytics may be more correct but heavier if queries are not indexed or aggregated carefully.

**Mitigation:** Performance check Phase 4C before adding richer charts.

---

## 7. Definition of Done for Cleanup Pass

The cleanup pass is complete when:

- [x] Remaining legacy dependencies are listed and prioritized
- [x] All meaningful IncidentUpdate usage is identified
- [x] Analytics candidates for event-backed migration are mapped
- [x] Queue logic gaps involving current_authority_id are documented
- [x] Phase 4 implementation order is agreed and recorded
- [x] Completed queue policy (Option A) is documented
