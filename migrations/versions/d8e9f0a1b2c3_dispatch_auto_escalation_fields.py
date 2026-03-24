"""Add auto-escalation reminder fields for incident_dispatches.

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa


revision = "d8e9f0a1b2c3"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "incident_dispatches",
        sa.Column("reminder_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("incident_dispatches", sa.Column("last_reminder_at", sa.DateTime(), nullable=True))
    op.add_column("incident_dispatches", sa.Column("next_reminder_at", sa.DateTime(), nullable=True))
    op.execute(
        """
        UPDATE incident_dispatches
        SET reminder_count = 0
        WHERE reminder_count IS NULL
        """
    )


def downgrade():
    op.drop_column("incident_dispatches", "next_reminder_at")
    op.drop_column("incident_dispatches", "last_reminder_at")
    op.drop_column("incident_dispatches", "reminder_count")
