"""Add admin audit logs

Revision ID: 0609d71ac819
Revises: e71b6a79eb68
Create Date: 2026-03-11 06:55:00.933227

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0609d71ac819'
down_revision = 'e71b6a79eb68'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'admin_audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('admin_user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('target_type', sa.String(length=32), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['admin_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index(
        op.f('ix_admin_audit_logs_admin_user_id'),
        'admin_audit_logs',
        ['admin_user_id'],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f('ix_admin_audit_logs_admin_user_id'), table_name='admin_audit_logs')
    op.drop_table('admin_audit_logs')
