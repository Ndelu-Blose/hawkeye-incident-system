"""Add structured location metadata fields to incidents.

Revision ID: k1l2m3n4o5p6
Revises: i0j1k2l3m4n5
Create Date: 2026-03-11

Adds:
- validated_address (normalized address string)
- suburb (normalized suburb/locality)
- ward (municipal ward identifier)
- location_validated (bool flag indicating geocoding/validation succeeded)
"""

from alembic import op
import sqlalchemy as sa


revision = "k1l2m3n4o5p6"
down_revision = "i0j1k2l3m4n5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("incidents", schema=None) as batch_op:
        batch_op.add_column(sa.Column("validated_address", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("suburb", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("ward", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column(
                "location_validated",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("FALSE"),
            )
        )


def downgrade():
    with op.batch_alter_table("incidents", schema=None) as batch_op:
        batch_op.drop_column("location_validated")
        batch_op.drop_column("ward")
        batch_op.drop_column("suburb")
        batch_op.drop_column("validated_address")

