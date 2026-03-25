"""Include route_applied in incident_events event_type constraint.

Revision ID: p2l0m1n2o3p4
Revises: p2f6a7b8c9d0
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa

from app.constants import IncidentEventType


revision = "p2l0m1n2o3p4"
down_revision = "p2f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    allowed_values = tuple(member.value for member in IncidentEventType)
    allowed_sql = ", ".join(f"'{value}'" for value in allowed_values)
    fallback = IncidentEventType.STATUS_CHANGED.value

    op.execute(
        sa.text(
            f"""
            UPDATE incident_events
            SET event_type = '{fallback}'
            WHERE event_type IS NULL OR event_type NOT IN ({allowed_sql})
            """
        )
    )

    with op.batch_alter_table("incident_events", schema=None) as batch_op:
        batch_op.drop_constraint(
            "ck_incident_events_event_type_allowed",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_incident_events_event_type_allowed",
            f"event_type IN ({allowed_sql})",
        )


def downgrade():
    # Downgrade is conservative: only allow the original set excluding route_applied.
    allowed_values = tuple(
        member.value
        for member in IncidentEventType
        if member
        not in {IncidentEventType.ROUTE_APPLIED}
    )
    old_sql = ", ".join(f"'{value}'" for value in allowed_values)

    with op.batch_alter_table("incident_events", schema=None) as batch_op:
        batch_op.drop_constraint(
            "ck_incident_events_event_type_allowed",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_incident_events_event_type_allowed",
            f"event_type IN ({old_sql})",
        )
