"""Merge migration heads

Revision ID: 65a6a37102a7
Revises: 140fd1a0121c, y4z5a6b7c8d9
Create Date: 2026-03-23 23:12:53.910479

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '65a6a37102a7'
down_revision = ("140fd1a0121c", "y4z5a6b7c8d9")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
