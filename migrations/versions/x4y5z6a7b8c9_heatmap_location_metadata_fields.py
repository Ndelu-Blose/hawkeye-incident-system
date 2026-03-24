"""Add hotspot/geocode metadata fields to incidents.

Revision ID: y4z5a6b7c8d9
Revises: x4y5z6a7b8c9
Create Date: 2026-03-23
"""

from alembic import op
import sqlalchemy as sa


revision = "y4z5a6b7c8d9"
down_revision = "x4y5z6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("incidents", sa.Column("location_precision", sa.String(length=32), nullable=True))
    op.add_column("incidents", sa.Column("geocoded_at", sa.DateTime(), nullable=True))
    op.add_column("incidents", sa.Column("geocode_source", sa.String(length=64), nullable=True))
    op.add_column(
        "incidents",
        sa.Column("hotspot_excluded", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    )


def downgrade():
    op.drop_column("incidents", "hotspot_excluded")
    op.drop_column("incidents", "geocode_source")
    op.drop_column("incidents", "geocoded_at")
    op.drop_column("incidents", "location_precision")
