# Dynamic Category Reporting Spec

## Overview

This feature makes resident incident reporting category-driven. Selecting a category now controls guided fields, generates a natural summary, and stores structured details for downstream admin and analytics use.

## Goals

- Improve report consistency and quality.
- Reduce resident confusion with guided prompts.
- Auto-generate usable incident summaries from structured answers.
- Preserve values when category changes where meaning overlaps.
- Persist structured incident details for triage and analytics.

## Non-Goals

- Full taxonomy rollout across every category in one release.
- Replacing free-text notes entirely.
- Admin-managed schema editor UI in this phase.

## MVP Categories

- `suspicious_activity`
- `theft`
- `vandalism`
- `noise_complaint`

## UX Rules

- Category selection drives guided details section.
- Title auto-fills from schema suggested title.
- Description auto-generates from guided answers + optional additional notes.
- Description remains editable by resident.
- If resident manually edits description, later auto-regeneration does not silently overwrite.
- Category change preserves compatible fields and warns before incompatible fields are dropped.

## Payload Contract

Resident submit payload includes:

- Core fields: `category_id`, `title`, `description`, `urgency_level`, location fields
- New fields:
  - `dynamic_details` (JSON object of guided answers)
  - `additional_notes` (optional free text)
  - `description_manually_edited` (client hint for overwrite safety)

## Validation

- Core existing validations remain.
- Category-aware validation applies required guided fields from schema.
- Unknown/non-MVP categories fall back to permissive schema.

## Persistence

- `incidents.dynamic_details` (JSON) stores structured guided answers.
- `incidents.additional_notes` stores free-text extras.
- `incidents.description` stores final user-visible summary text.

## Admin Consumption

Authority incident detail view renders:

- Incident Summary (`description`)
- Structured Details (`dynamic_details`)
- Additional Notes (`additional_notes`)

## Acceptance Criteria

- Resident can submit incidents with guided details for MVP categories.
- Generated descriptions are present without requiring manual description typing.
- Manual edits to description are respected.
- Category switch shows confirmation when destructive drops are detected.
- Structured details are persisted and visible to authorities.
