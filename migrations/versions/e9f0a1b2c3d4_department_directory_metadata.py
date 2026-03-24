"""Add department directory metadata fields.

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa


revision = "e9f0a1b2c3d4"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("authorities", sa.Column("physical_address", sa.String(length=255), nullable=True))
    op.add_column("authorities", sa.Column("operating_hours", sa.String(length=120), nullable=True))
    op.add_column("authorities", sa.Column("service_hub", sa.String(length=120), nullable=True))

    op.add_column(
        "department_contacts",
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "department_contacts",
        sa.Column("is_secondary", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "department_contacts",
        sa.Column("verification_status", sa.String(length=24), nullable=False, server_default="unverified"),
    )
    op.add_column("department_contacts", sa.Column("source_url", sa.String(length=512), nullable=True))
    op.add_column("department_contacts", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column(
        "department_contacts",
        sa.Column("after_hours", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_index(
        "ix_department_contacts_is_primary",
        "department_contacts",
        ["is_primary"],
        unique=False,
    )
    op.create_index(
        "ix_department_contacts_is_secondary",
        "department_contacts",
        ["is_secondary"],
        unique=False,
    )
    op.create_index(
        "ix_department_contacts_verification_status",
        "department_contacts",
        ["verification_status"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_department_contacts_verification_status", table_name="department_contacts")
    op.drop_index("ix_department_contacts_is_secondary", table_name="department_contacts")
    op.drop_index("ix_department_contacts_is_primary", table_name="department_contacts")
    op.drop_column("department_contacts", "after_hours")
    op.drop_column("department_contacts", "notes")
    op.drop_column("department_contacts", "source_url")
    op.drop_column("department_contacts", "verification_status")
    op.drop_column("department_contacts", "is_secondary")
    op.drop_column("department_contacts", "is_primary")

    op.drop_column("authorities", "service_hub")
    op.drop_column("authorities", "operating_hours")
    op.drop_column("authorities", "physical_address")
