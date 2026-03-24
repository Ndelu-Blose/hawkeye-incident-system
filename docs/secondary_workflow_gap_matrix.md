# Secondary Workflow Gap Matrix

| Stage | Current state | Gap previously identified | Enhancement now applied | Evidence |
|---|---|---|---|---|
| Incident submission | Implemented | None major | Preserved | `app/routes/resident_routes.py`, `app/services/incident_service.py#create_incident` |
| Admin verification | Partially implemented | No explicit proof verification state | Added formal verification fields + admin proof actions | `app/models/incident.py`, `app/routes/admin_routes.py`, `app/templates/admin/incidents/detail.html` |
| Request additional proof | Missing | No structured loop for weak evidence | Added `awaiting_evidence` status and admin request flow; resident re-submission loop | `app/constants.py`, `app/services/incident_service.py#request_additional_proof`, `#attach_media` |
| Escalate to authority (email) | Partial (queued only) | No send/track processing | Added queued notification processing and status updates | `app/services/notification_service.py#process_queued`, `scripts/process_notifications.py` |
| Capture authority response | Implemented baseline | Semantics too generic | Added event-type distinctions for progress/resolution | `app/constants.py`, `app/services/incident_service.py#_event_type_for_transition` |
| Show authority response to resident | Implemented baseline | Not strongly semantic in timeline | Added timeline mappings for proof request and authority response events | `app/services/incident_service.py#_event_to_timeline`, resident/authority detail templates |
| Ongoing updates | Implemented baseline | Proof-request loop missing | Loop completed (request -> resubmit -> back to review) | `app/services/incident_service.py`, `app/templates/resident/incident_detail.html` |
| Resolution | Implemented | None major | Preserved + stronger milestone tracking | `app/services/incident_service.py#change_status` |
| Lifecycle language alignment | Partial mismatch | `screened/assigned` vs `verified/escalated` | Added business-term mapping hints in UI | admin/authority/resident incident detail templates |
| Audit depth | Partial | Missing explicit proof-review audit actions | Added proof-related audit writes | `app/services/incident_service.py` + `app/services/audit_service.py` |

## Remaining future improvements

- Add dedicated authority response entity if threaded official correspondence is required.
- Add async background worker for notification sending at scale (queue backend).
- Consider full enum/status rename migration if business requires native `verified/escalated` status labels at database level.

