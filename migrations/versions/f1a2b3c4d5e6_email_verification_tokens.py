"""email verification tokens

Revision ID: f1a2b3c4d5e6
Revises: 6ff356fa4d02
Create Date: 2026-04-07

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "6ff356fa4d02"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("email_verification_token", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("email_verification_expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_users_email_verification_token",
        "users",
        ["email_verification_token"],
        unique=False,
    )
    # Existing accounts should keep working without going through Resend.
    op.execute(sa.text("UPDATE users SET email_verified = true"))


def downgrade():
    op.drop_index("ix_users_email_verification_token", table_name="users")
    op.drop_column("users", "email_verification_expires_at")
    op.drop_column("users", "email_verification_token")
