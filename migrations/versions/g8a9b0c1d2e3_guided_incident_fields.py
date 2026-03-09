"""Add guided incident wizard fields to incidents.

Revision ID: g8a9b0c1d2e3
Revises: f7a8b9c0d1e2
Create Date: 2026-03-06

"""
from alembic import op
import sqlalchemy as sa


revision = "g8a9b0c1d2e3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "incidents",
        sa.Column("location_mode", sa.String(32), nullable=True),
    )
    op.add_column(
        "incidents",
        sa.Column("is_happening_now", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "incidents",
        sa.Column("is_anyone_in_danger", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "incidents",
        sa.Column("is_issue_still_present", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "incidents",
        sa.Column("urgency_level", sa.String(32), nullable=True),
    )


def downgrade():
    op.drop_column("incidents", "urgency_level")
    op.drop_column("incidents", "is_issue_still_present")
    op.drop_column("incidents", "is_anyone_in_danger")
    op.drop_column("incidents", "is_happening_now")
    op.drop_column("incidents", "location_mode")
