"""Add incident dynamic details and additional notes fields.

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
Create Date: 2026-03-23 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "x4y5z6a7b8c9"
down_revision = "w3x4y5z6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("incidents", sa.Column("additional_notes", sa.Text(), nullable=True))
    op.add_column("incidents", sa.Column("dynamic_details", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("incidents", "dynamic_details")
    op.drop_column("incidents", "additional_notes")
