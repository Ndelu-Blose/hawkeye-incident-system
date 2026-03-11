"""Add admin preferences

Revision ID: 198053cb6a01
Revises: 0609d71ac819
Create Date: 2026-03-11 07:30:21.388508

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '198053cb6a01'
down_revision = '0609d71ac819'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "admin_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("show_kpi_cards", sa.Boolean(), nullable=False),
        sa.Column("show_recent_incidents", sa.Boolean(), nullable=False),
        sa.Column("show_overdue_panel", sa.Boolean(), nullable=False),
        sa.Column("show_user_stats", sa.Boolean(), nullable=False),
        sa.Column("notify_new_incident", sa.Boolean(), nullable=False),
        sa.Column("notify_overdue_incident", sa.Boolean(), nullable=False),
        sa.Column("daily_summary_enabled", sa.Boolean(), nullable=False),
        sa.Column("default_landing_page", sa.String(length=32), nullable=False),
        sa.Column("default_incident_sort", sa.String(length=32), nullable=False),
        sa.Column("default_rows_per_page", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        op.f("ix_admin_preferences_user_id"),
        "admin_preferences",
        ["user_id"],
        unique=True,
    )


def downgrade():
    op.drop_index(op.f("ix_admin_preferences_user_id"), table_name="admin_preferences")
    op.drop_table("admin_preferences")
