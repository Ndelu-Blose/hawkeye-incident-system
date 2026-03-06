"""Backfill reported_at and reference_no for existing incidents.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-03-06

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE incidents SET reported_at = created_at WHERE reported_at IS NULL"
    )
    op.execute(
        "UPDATE incidents SET reference_no = 'HKY-' || LPAD(id::text, 6, '0') "
        "WHERE reference_no IS NULL AND id IS NOT NULL"
    )


def downgrade():
    # Cannot reliably reverse reference_no backfill; leave as-is.
    pass
