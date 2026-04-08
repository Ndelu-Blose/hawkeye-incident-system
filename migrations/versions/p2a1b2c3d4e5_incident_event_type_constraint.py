"""Enforce controlled incident event types.

Revision ID: p2a1b2c3d4e5
Revises: n1p2q3r4s5t6
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa

from app.constants import IncidentEventType


# revision identifiers, used by Alembic.
revision = "p2a1b2c3d4e5"
down_revision = "n1p2q3r4s5t6"
branch_labels = None
depends_on = None


def upgrade():
    allowed_values = tuple(member.value for member in IncidentEventType)
    allowed_sql = ", ".join(f"'{value}'" for value in allowed_values)
    op.execute(
        sa.text(
            f"""
            UPDATE incident_events
            SET event_type = 'status_changed'
            WHERE event_type IS NULL OR event_type NOT IN ({allowed_sql})
            """
        )
    )

    with op.batch_alter_table("incident_events", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "ck_incident_events_event_type_allowed",
            f"event_type IN ({allowed_sql})",
        )


def downgrade():
    with op.batch_alter_table("incident_events", schema=None) as batch_op:
        batch_op.drop_constraint("ck_incident_events_event_type_allowed", type_="check")
