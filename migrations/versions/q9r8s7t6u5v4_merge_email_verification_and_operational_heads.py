"""merge email verification and operational heads

Revision ID: q9r8s7t6u5v4
Revises: f1a2b3c4d5e6, p2l0m1n2o3p4
Create Date: 2026-04-08 14:07:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "q9r8s7t6u5v4"
down_revision = ("f1a2b3c4d5e6", "p2l0m1n2o3p4")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
