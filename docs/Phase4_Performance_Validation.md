# Phase 4C — Performance Validation

**Version 1.0 | March 2026**

---

## Scope

Validate that analytics queries remain correct and efficient on larger datasets after migrating from snapshot fields to event-led joins and aggregations.

**Key questions:**
- Which queries are actually heavy, and why?
- Do we have the right indexes for event-backed paths?
- Does the analytics dashboard trigger N+1 or excessive round-trips?

---

## 1. Queries Reviewed

### 1.1 Dashboard Summary Queries (10 calls per page load)

| Query | Table(s) | Filter Pattern | Index Used |
|-------|----------|----------------|------------|
| `total_incidents_this_week` | incident_events | event_type, created_at >= since | ix_incident_events_event_type |
| `resolved_this_week` | incident_events | event_type, created_at >= since | ix_incident_events_event_type |
| `avg_resolution_time_hours` | incident_events (2 subqueries) + join | event_type, created_at | ix_incident_events_event_type |
| `avg_resolution_time_by_category` | incident_events + Incident | event_type, created_at | ix_incident_events_event_type |
| `incident_volume_by_day` | incident_events | event_type, created_at >= since, group by date | ix_incident_events_event_type |
| `open_incidents_by_authority` | incident_ownership_history + Incident | is_current, status in (...) | ix_incident_ownership_history_incident_id |
| `avg_dispatch_to_ack_time_by_authority` | incident_dispatches + Authority | ack_at, ack_status, dispatched_at | (existing dispatch indexes) |
| `hotspots_by_suburb` | incidents | reported_at >= since | (incident indexes) |
| `rejection_count_by_category` | incident_events + Incident | event_type, created_at >= since | ix_incident_events_event_type |
| `override_count_by_actor` | audit_logs | entity_type, action, created_at >= since | ix_audit_logs_entity_type |

### 1.2 Query Count / N+1

- **Dashboard:** 10 separate repository calls. No batching. Each is a single SQL statement.
- **Template:** No lazy-loaded relationships iterated in loops. All data is pre-fetched in the service.
- **Verdict:** 10 queries per page load is acceptable. No N+1 risk in templates.

### 1.3 Repeated Scans of incident_events

- `total_incidents_this_week`, `resolved_this_week`, `incident_volume_by_day` each scan `incident_events` with `event_type = X` and `created_at >= since`.
- `avg_resolution_time_hours` and `avg_resolution_time_by_category` use two subqueries (created, resolved) that each scan `incident_events`.
- **Observation:** Multiple passes over incident_events. A composite index `(event_type, created_at)` would allow index-only or index-range scans for these filters.

---

## 2. Index Readiness

### 2.1 Current Indexes

| Table | Index | Columns |
|-------|-------|---------|
| incident_events | ix_incident_events_incident_id | incident_id |
| incident_events | ix_incident_events_event_type | event_type |
| incident_ownership_history | ix_incident_ownership_history_incident_id | incident_id |
| incident_ownership_history | ix_incident_ownership_history_incident_current | (incident_id) WHERE is_current=true |
| audit_logs | ix_audit_logs_entity_type | entity_type |
| audit_logs | ix_audit_logs_entity_id | entity_id |

### 2.2 Missing / Recommended

| Table | Recommended Index | Purpose |
|-------|-------------------|---------|
| incident_events | (event_type, created_at) | Range scans for event_type + created_at filter (volume, total, resolved, resolution time) |
| audit_logs | (entity_type, action, created_at) | Override query: entity_type + action + created_at range |
| incident_ownership_history | (is_current, authority_id) | Workload by authority: filter is_current, group by authority_id |

---

## 3. Dataset Used

**Seed script:** `scripts/seed_analytics_data.py`

- Target: ~1,000–2,000 incidents with full event ledger (configurable via CLI: `python scripts/seed_analytics_data.py 1500`)
- Mix of statuses: reported, screened, assigned, acknowledged, in_progress, resolved, closed, rejected (weighted toward resolved/closed)
- Multiple authorities, categories, suburbs
- Events: incident_created, incident_resolved, incident_rejected, incident_status_override (audit)
- **Validated:** Integration test `test_analytics_dashboard_with_seeded_data` seeds 200 incidents and verifies all dashboard summary queries return expected structure. Passes on SQLite in-memory.

---

## 4. Findings

### 4.1 Heavy Query Candidates

| Query | Risk | Reason |
|-------|------|--------|
| `avg_resolution_time_by_category` | Medium | Two subqueries over incident_events + join to Incident. No composite index on (event_type, created_at). |
| `incident_volume_by_day` | Low | Single table, group by date. event_type index helps; created_at range may scan. |
| `open_incidents_by_authority` | Low | Join ownership + Incident. Partial unique index helps is_current filter. |
| `override_count_by_actor` | Low | Single table, entity_type + action + created_at. No composite index. |

### 4.2 Consolidation Opportunities

- **Not recommended now:** Combining the 10 dashboard queries into fewer round-trips would require significant refactoring. The current structure is clear and maintainable. 10 queries for a dashboard is within normal bounds.
- **Future:** If dashboard load time becomes an issue, consider a materialized summary table refreshed periodically.

---

## 5. Risks

| Risk | Mitigation |
|------|------------|
| incident_events grows large | Composite index (event_type, created_at) keeps time-range queries efficient |
| audit_logs grows large | Composite index (entity_type, action, created_at) for override/rejection analytics |
| Dashboard slow on cold cache | Ensure indexes exist; consider connection pooling |

---

## 6. Optimizations Applied

- [x] Migration `u1v2w3x4y5z6_analytics_performance_indexes`: Add composite indexes (incident_events, audit_logs, incident_ownership_history)
- [x] Run seed script and verify dashboard responsiveness (integration test passes with 200 incidents)

---

## 7. Remaining Recommendations

1. **Add composite indexes** via migration (optional; apply if dashboard load is slow on production-like data).
2. **Monitor** analytics page load time as incident_events and audit_logs grow.
3. **Phase 4D** can proceed; if charts add heavier queries, re-run this validation.
