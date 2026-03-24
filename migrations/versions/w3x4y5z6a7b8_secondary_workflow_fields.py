"""Add secondary workflow verification and escalation fields.

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-03-23
"""

from alembic import op
import sqlalchemy as sa


revision = "w3x4y5z6a7b8"
down_revision = "v2w3x4y5z6a7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "incidents",
        sa.Column("verification_status", sa.String(length=32), nullable=False, server_default="pending"),
    )
    op.add_column("incidents", sa.Column("verification_notes", sa.Text(), nullable=True))
    op.add_column("incidents", sa.Column("verified_at", sa.DateTime(), nullable=True))
    op.add_column("incidents", sa.Column("verified_by_user_id", sa.Integer(), nullable=True))
    op.add_column("incidents", sa.Column("proof_requested_at", sa.DateTime(), nullable=True))
    op.add_column("incidents", sa.Column("proof_requested_by_user_id", sa.Integer(), nullable=True))
    op.add_column("incidents", sa.Column("proof_request_reason", sa.Text(), nullable=True))
    op.add_column("incidents", sa.Column("evidence_resubmitted_at", sa.DateTime(), nullable=True))
    op.add_column("incidents", sa.Column("escalated_at", sa.DateTime(), nullable=True))
    op.add_column("incidents", sa.Column("escalated_by_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_incidents_verified_by_user_id_users",
        "incidents",
        "users",
        ["verified_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_incidents_proof_requested_by_user_id_users",
        "incidents",
        "users",
        ["proof_requested_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_incidents_escalated_by_user_id_users",
        "incidents",
        "users",
        ["escalated_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_incidents_verification_status",
        "incidents",
        ["verification_status"],
        unique=False,
    )

    conn = op.get_bind()
    if conn.dialect.name != "sqlite":
        op.alter_column("incidents", "verification_status", server_default=None)


def downgrade():
    op.drop_index("ix_incidents_verification_status", table_name="incidents")
    op.drop_constraint("fk_incidents_escalated_by_user_id_users", "incidents", type_="foreignkey")
    op.drop_constraint(
        "fk_incidents_proof_requested_by_user_id_users",
        "incidents",
        type_="foreignkey",
    )
    op.drop_constraint("fk_incidents_verified_by_user_id_users", "incidents", type_="foreignkey")
    op.drop_column("incidents", "escalated_by_user_id")
    op.drop_column("incidents", "escalated_at")
    op.drop_column("incidents", "evidence_resubmitted_at")
    op.drop_column("incidents", "proof_request_reason")
    op.drop_column("incidents", "proof_requested_by_user_id")
    op.drop_column("incidents", "proof_requested_at")
    op.drop_column("incidents", "verified_by_user_id")
    op.drop_column("incidents", "verified_at")
    op.drop_column("incidents", "verification_notes")
    op.drop_column("incidents", "verification_status")

