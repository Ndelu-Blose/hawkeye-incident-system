# Hawkeye Secondary Workflow Implementation Plan

## Purpose

Hawkeye's secondary function is a full incident escalation lifecycle: submit -> verify -> escalate -> respond -> resolve. This plan formalizes that workflow so actions are auditable, resident-visible, and operationally reliable.

## Current capability baseline

- Incident submission with evidence and timeline/event creation is implemented.
- Canonical lifecycle engine exists in `IncidentService.change_status(...)`.
- Authority acknowledgment/status updates are implemented.
- Resident timeline + notifications are implemented.

## Implemented enhancements in this pass

1. **Workflow centralization hardening**
   - `admin` screening confirmation now uses service-layer canonical flow.
   - Route-level direct assignment/dispatch mutation is replaced by service orchestration.
   - Files:
     - `app/routes/admin_routes.py`
     - `app/services/incident_service.py`

2. **Formal proof verification model**
   - Added explicit verification metadata on `Incident`:
     - `verification_status`, `verification_notes`
     - `verified_at`, `verified_by_user_id`
     - `proof_requested_at`, `proof_requested_by_user_id`, `proof_request_reason`
     - `evidence_resubmitted_at`
     - `escalated_at`, `escalated_by_user_id`
   - Added migration for these fields.
   - Files:
     - `app/models/incident.py`
     - `migrations/versions/w3x4y5z6a7b8_secondary_workflow_fields.py`

3. **Request-additional-proof loop**
   - Added lifecycle status `awaiting_evidence`.
   - Added admin actions to request additional proof and record proof review decisions.
   - Resident re-submission via media upload returns incident from `awaiting_evidence` -> `reported`.
   - Files:
     - `app/constants.py`
     - `app/services/incident_service.py`
     - `app/routes/admin_routes.py`
     - `app/templates/admin/incidents/detail.html`
     - `app/templates/resident/incident_detail.html`

4. **Authority escalation delivery pipeline**
   - Added notification outbox processing method for queued entries.
   - Added send/fail status updates (`sent_at`, `last_error`).
   - Added script entrypoint for batch processing.
   - Files:
     - `app/services/notification_service.py`
     - `scripts/process_notifications.py`

5. **Structured response semantics**
   - Added event types:
     - `proof_requested`
     - `authority_progress_update`
     - `authority_resolution_update`
   - Timeline mapping now distinguishes these events.
   - Files:
     - `app/constants.py`
     - `app/services/incident_service.py`
     - `app/routes/authority_routes.py`
     - `app/templates/authority/incident_detail.html`

6. **Terminology alignment**
   - UI hints now map internal lifecycle wording:
     - `screened` -> `Verified`
     - `assigned` -> `Escalated`
   - Files:
     - `app/templates/admin/incidents/detail.html`
     - `app/templates/authority/incident_detail.html`
     - `app/templates/resident/incident_detail.html`

7. **Audit and milestone depth**
   - Added audit actions for proof verification/rejection/proof-request.
   - Added escalation and verification milestone timestamps/actors on incident.
   - Files:
     - `app/services/incident_service.py`
     - `app/services/audit_service.py` (used)

## Validation strategy

- Added integration tests covering:
  - canonical screening confirmation path and escalation artifacts
  - proof-request/resubmission loop behavior
  - queued notification processing updates
- File:
  - `tests/integration/test_secondary_workflow.py`

## Operational notes

- Notification delivery uses Flask-Mail and application config.
- Production scheduling can call:
  - `python -m scripts.process_notifications`
- This can be run via cron/job runner until a dedicated async worker is introduced.

