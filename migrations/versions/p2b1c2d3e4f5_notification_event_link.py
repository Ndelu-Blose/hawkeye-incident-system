"""Link notifications to causative incident events.

Revision ID: p2b1c2d3e4f5
Revises: p2a1b2c3d4e5
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "p2b1c2d3e4f5"
down_revision = "p2a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("notification_log", schema=None) as batch_op:
        batch_op.add_column(sa.Column("event_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_notification_log_event_id"), ["event_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_notification_log_event_id_incident_events",
            "incident_events",
            ["event_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade():
    with op.batch_alter_table("notification_log", schema=None) as batch_op:
        batch_op.drop_constraint("fk_notification_log_event_id_incident_events", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_notification_log_event_id"))
        batch_op.drop_column("event_id")
