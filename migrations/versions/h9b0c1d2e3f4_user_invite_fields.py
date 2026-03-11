"""Add user invite token and expiry for set-password flow.

Revision ID: h9b0c1d2e3f4
Revises: g8a9b0c1d2e3
Create Date: 2026-03-10

"""
from alembic import op
import sqlalchemy as sa


revision = "h9b0c1d2e3f4"
down_revision = "g8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("invite_token", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("invite_expires_at", sa.DateTime(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_users_invite_token"),
            ["invite_token"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_invite_token"), table_name="users")
        batch_op.drop_column("invite_expires_at")
        batch_op.drop_column("invite_token")
