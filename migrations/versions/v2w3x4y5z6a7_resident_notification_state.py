"""Add resident_notification_state table for unread notifications.

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
Create Date: 2026-03-18
"""

from alembic import op
import sqlalchemy as sa


revision = "v2w3x4y5z6a7"
down_revision = "u1v2w3x4y5z6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "resident_notification_state",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_resident_notification_state_user_id",
        "resident_notification_state",
        ["user_id"],
        unique=True,
    )
    op.create_index(
        "ix_resident_notification_state_last_seen_at",
        "resident_notification_state",
        ["last_seen_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_resident_notification_state_last_seen_at",
        table_name="resident_notification_state",
    )
    op.drop_index(
        "ix_resident_notification_state_user_id",
        table_name="resident_notification_state",
    )
    op.drop_table("resident_notification_state")

