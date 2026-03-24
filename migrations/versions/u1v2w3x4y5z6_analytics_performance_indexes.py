"""Add composite indexes for analytics performance (Phase 4C).

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
Create Date: 2026-03-11

Phase 4C: Optimize event-backed analytics queries.
"""
from alembic import op

revision = "u1v2w3x4y5z6"
down_revision = "t0u1v2w3x4y5"
branch_labels = None
depends_on = None


def upgrade():
    # incident_events: (event_type, created_at) for volume, total, resolved, resolution time
    op.create_index(
        "ix_incident_events_event_type_created_at",
        "incident_events",
        ["event_type", "created_at"],
        unique=False,
    )
    # audit_logs: (entity_type, action, created_at) for override/rejection analytics
    op.create_index(
        "ix_audit_logs_entity_type_action_created_at",
        "audit_logs",
        ["entity_type", "action", "created_at"],
        unique=False,
    )
    # incident_ownership_history: (is_current, authority_id) for workload by authority
    op.create_index(
        "ix_incident_ownership_history_is_current_authority",
        "incident_ownership_history",
        ["is_current", "authority_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_incident_ownership_history_is_current_authority",
        table_name="incident_ownership_history",
    )
    op.drop_index(
        "ix_audit_logs_entity_type_action_created_at",
        table_name="audit_logs",
    )
    op.drop_index(
        "ix_incident_events_event_type_created_at",
        table_name="incident_events",
    )
