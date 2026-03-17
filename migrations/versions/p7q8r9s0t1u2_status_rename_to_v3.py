"""Rename incident status values to v3 lifecycle vocabulary.

Revision ID: p7q8r9s0t1u2
Revises: k1l2m3n4o5p6
Create Date: 2026-03-11

Maps:
- pending  -> reported
- verified -> screened
"""

from alembic import op


revision = "p7q8r9s0t1u2"
down_revision = "k1l2m3n4o5p6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE incidents SET status = 'reported' WHERE status = 'pending'")
    op.execute("UPDATE incidents SET status = 'screened' WHERE status = 'verified'")


def downgrade():
    op.execute("UPDATE incidents SET status = 'pending' WHERE status = 'reported'")
    op.execute("UPDATE incidents SET status = 'verified' WHERE status = 'screened'")

