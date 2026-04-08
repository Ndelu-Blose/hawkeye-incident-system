"""Update incident_events event_type constraint for routing events.

Revision ID: p2f6a7b8c9d0
Revises: p2d1e2f3g4h5
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa

from app.constants import IncidentEventType


# revision identifiers, used by Alembic.
revision = "p2f6a7b8c9d0"
down_revision = "p2d1e2f3g4h5"
branch_labels = None
depends_on = None


def _allowed_sql(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade():
    allowed_values = tuple(member.value for member in IncidentEventType)
    allowed_sql = _allowed_sql(allowed_values)
    fallback = IncidentEventType.STATUS_CHANGED.value

    # Ensure existing rows always satisfy the updated constraint.
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
    old_values = tuple(
        member.value
        for member in IncidentEventType
        if member
        not in {
            IncidentEventType.ROUTE_SUGGESTED,
            IncidentEventType.ROUTING_FAILED,
            IncidentEventType.ROUTING_OVERRIDDEN,
        }
    )
    old_sql = _allowed_sql(old_values)

    with op.batch_alter_table("incident_events", schema=None) as batch_op:
        batch_op.drop_constraint(
            "ck_incident_events_event_type_allowed",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_incident_events_event_type_allowed",
            f"event_type IN ({old_sql})",
        )

