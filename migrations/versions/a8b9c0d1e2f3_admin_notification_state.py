"""Add admin_notification_state table for unread admin notifications.

Revision ID: a8b9c0d1e2f3
Revises: z5a6b7c8d9e0
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa


revision = "a8b9c0d1e2f3"
down_revision = "z5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "admin_notification_state",
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
        "ix_admin_notification_state_user_id",
        "admin_notification_state",
        ["user_id"],
        unique=True,
    )
    op.create_index(
        "ix_admin_notification_state_last_seen_at",
        "admin_notification_state",
        ["last_seen_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_admin_notification_state_last_seen_at",
        table_name="admin_notification_state",
    )
    op.drop_index(
        "ix_admin_notification_state_user_id",
        table_name="admin_notification_state",
    )
    op.drop_table("admin_notification_state")
