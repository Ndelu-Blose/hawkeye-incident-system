"""Add workflow and dashboard indexes for incidents.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-03-06

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("incidents", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_incidents_reported_at"),
            ["reported_at"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_incidents_category_id"),
            ["category_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_incidents_authority_status",
            ["current_authority_id", "status"],
            unique=False,
        )
        batch_op.create_index(
            "ix_incidents_location_status",
            ["location_id", "status"],
            unique=False,
        )
        batch_op.create_index(
            "ix_incidents_category_status",
            ["category_id", "status"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("incidents", schema=None) as batch_op:
        batch_op.drop_index("ix_incidents_category_status", table_name="incidents")
        batch_op.drop_index("ix_incidents_location_status", table_name="incidents")
        batch_op.drop_index("ix_incidents_authority_status", table_name="incidents")
        batch_op.drop_index(
            batch_op.f("ix_incidents_category_id"),
            table_name="incidents",
        )
        batch_op.drop_index(
            batch_op.f("ix_incidents_reported_at"),
            table_name="incidents",
        )
