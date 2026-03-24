"""Repair missing incident columns on drifted databases.

Revision ID: z5a6b7c8d9e0
Revises: 65a6a37102a7
Create Date: 2026-03-24 08:45:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "z5a6b7c8d9e0"
down_revision = "65a6a37102a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Some environments were stamped to head without these columns applied.
    # Use IF NOT EXISTS to keep this migration idempotent and safe.
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS additional_notes TEXT")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS dynamic_details JSON")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS location_precision VARCHAR(32)")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS geocoded_at TIMESTAMP")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS geocode_source VARCHAR(64)")
    op.execute(
        "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS hotspot_excluded BOOLEAN DEFAULT FALSE NOT NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE incidents DROP COLUMN IF EXISTS hotspot_excluded")
    op.execute("ALTER TABLE incidents DROP COLUMN IF EXISTS geocode_source")
    op.execute("ALTER TABLE incidents DROP COLUMN IF EXISTS geocoded_at")
    op.execute("ALTER TABLE incidents DROP COLUMN IF EXISTS location_precision")
    op.execute("ALTER TABLE incidents DROP COLUMN IF EXISTS dynamic_details")
    op.execute("ALTER TABLE incidents DROP COLUMN IF EXISTS additional_notes")
