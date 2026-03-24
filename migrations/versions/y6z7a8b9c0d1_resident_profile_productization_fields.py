"""Add resident profile productization fields.

Revision ID: y6z7a8b9c0d1
Revises: v2w3x4y5z6a7
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa


revision = "y6z7a8b9c0d1"
down_revision = "v2w3x4y5z6a7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "resident_profiles",
        sa.Column("share_anonymous_analytics", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "resident_profiles",
        sa.Column("notify_incident_updates", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "resident_profiles",
        sa.Column("notify_status_changes", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "resident_profiles",
        sa.Column("notify_community_alerts", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("resident_profiles", sa.Column("avatar_filename", sa.String(length=255), nullable=True))

    op.alter_column("resident_profiles", "share_anonymous_analytics", server_default=None)
    op.alter_column("resident_profiles", "notify_incident_updates", server_default=None)
    op.alter_column("resident_profiles", "notify_status_changes", server_default=None)
    op.alter_column("resident_profiles", "notify_community_alerts", server_default=None)


def downgrade():
    op.drop_column("resident_profiles", "avatar_filename")
    op.drop_column("resident_profiles", "notify_community_alerts")
    op.drop_column("resident_profiles", "notify_status_changes")
    op.drop_column("resident_profiles", "notify_incident_updates")
    op.drop_column("resident_profiles", "share_anonymous_analytics")
