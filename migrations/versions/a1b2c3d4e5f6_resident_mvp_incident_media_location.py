"""Resident MVP: incident location fields and incident_media table

Revision ID: a1b2c3d4e5f6
Revises: 8edd7ab1729f
Create Date: 2026-03-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "8edd7ab1729f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "incidents",
        sa.Column("suburb_or_ward", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "incidents",
        sa.Column("street_or_landmark", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "incidents",
        sa.Column("nearest_place", sa.String(length=255), nullable=True),
    )
    op.execute(
        "UPDATE incidents SET suburb_or_ward = 'Unknown', street_or_landmark = COALESCE(location, '') WHERE suburb_or_ward IS NULL"
    )
    op.alter_column(
        "incidents",
        "suburb_or_ward",
        existing_type=sa.String(120),
        nullable=False,
    )
    op.alter_column(
        "incidents",
        "street_or_landmark",
        existing_type=sa.String(255),
        nullable=False,
    )

    op.create_table(
        "incident_media",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("filesize_bytes", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("incident_media", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_incident_media_incident_id"),
            ["incident_id"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("incident_media", schema=None) as batch_op:
        batch_op.drop_index(
            batch_op.f("ix_incident_media_incident_id"),
            table_name="incident_media",
        )
    op.drop_table("incident_media")
    op.drop_column("incidents", "nearest_place")
    op.drop_column("incidents", "street_or_landmark")
    op.drop_column("incidents", "suburb_or_ward")
