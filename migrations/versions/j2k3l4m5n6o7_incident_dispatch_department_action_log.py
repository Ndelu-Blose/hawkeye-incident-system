"""Incident dispatch and department action log tables.

Revision ID: j2k3l4m5n6o7
Revises: p7q8r9s0t1u2
Create Date: 2026-03-11

Phase 3.5: Dispatch records and department action logging.
"""
from alembic import op
import sqlalchemy as sa


revision = "j2k3l4m5n6o7"
down_revision = "p7q8r9s0t1u2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "incident_dispatches",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "incident_assignment_id",
            sa.Integer(),
            sa.ForeignKey("incident_assignments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "incident_id",
            sa.Integer(),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "authority_id",
            sa.Integer(),
            sa.ForeignKey("authorities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dispatch_method",
            sa.String(length=32),
            nullable=False,
            server_default="internal_queue",
        ),
        sa.Column("dispatched_by_type", sa.String(length=32), nullable=False),
        sa.Column(
            "dispatched_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("destination_reference", sa.String(length=255), nullable=True),
        sa.Column(
            "delivery_status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("delivery_status_detail", sa.Text(), nullable=True),
        sa.Column(
            "ack_status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "ack_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ack_at", sa.DateTime(), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(), nullable=False),
        sa.Column("delivery_confirmed_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_incident_dispatches_incident_id",
        "incident_dispatches",
        ["incident_id"],
        unique=False,
    )

    op.create_table(
        "department_action_logs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "incident_id",
            sa.Integer(),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "authority_id",
            sa.Integer(),
            sa.ForeignKey("authorities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "performed_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_department_action_logs_incident_id",
        "department_action_logs",
        ["incident_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_department_action_logs_incident_id",
        table_name="department_action_logs",
    )
    op.drop_table("department_action_logs")
    op.drop_index(
        "ix_incident_dispatches_incident_id",
        table_name="incident_dispatches",
    )
    op.drop_table("incident_dispatches")
