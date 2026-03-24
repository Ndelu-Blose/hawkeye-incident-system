"""Add authority production fields and department contacts.

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa


revision = "c7d8e9f0a1b2"
down_revision = "b6c7d8e9f0a1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("authorities", sa.Column("code", sa.String(length=80), nullable=True))
    op.add_column(
        "authorities",
        sa.Column("routing_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "authorities",
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_authorities_code", "authorities", ["code"], unique=True)

    op.create_table(
        "department_contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("authority_id", sa.Integer(), nullable=False),
        sa.Column("contact_type", sa.String(length=24), nullable=False, server_default="primary"),
        sa.Column("channel", sa.String(length=24), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["authority_id"], ["authorities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "authority_id",
            "contact_type",
            "channel",
            "value",
            name="uq_department_contact_per_authority",
        ),
    )
    op.create_index(
        "ix_department_contacts_authority_id",
        "department_contacts",
        ["authority_id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_department_contacts_authority_id", table_name="department_contacts")
    op.drop_table("department_contacts")
    op.drop_index("ix_authorities_code", table_name="authorities")
    op.drop_column("authorities", "notifications_enabled")
    op.drop_column("authorities", "routing_enabled")
    op.drop_column("authorities", "code")
