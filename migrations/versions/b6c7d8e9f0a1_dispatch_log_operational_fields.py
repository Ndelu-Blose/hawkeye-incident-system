"""Extend incident_dispatches with operational dispatch log fields.

Revision ID: b6c7d8e9f0a1
Revises: 65a6a37102a7
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa


revision = "b6c7d8e9f0a1"
down_revision = "65a6a37102a7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("incident_dispatches", sa.Column("status", sa.String(length=30), nullable=True))
    op.add_column(
        "incident_dispatches", sa.Column("recipient_email", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "incident_dispatches", sa.Column("subject_snapshot", sa.String(length=255), nullable=True)
    )
    op.add_column("incident_dispatches", sa.Column("message_snapshot", sa.Text(), nullable=True))
    op.add_column(
        "incident_dispatches", sa.Column("delivery_provider", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "incident_dispatches", sa.Column("delivery_reference", sa.String(length=255), nullable=True)
    )
    op.add_column("incident_dispatches", sa.Column("failure_reason", sa.Text(), nullable=True))
    op.add_column(
        "incident_dispatches",
        sa.Column("external_reference_number", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "incident_dispatches",
        sa.Column("external_reference_source", sa.String(length=120), nullable=True),
    )
    op.add_column("incident_dispatches", sa.Column("delivered_at", sa.DateTime(), nullable=True))
    op.add_column("incident_dispatches", sa.Column("resolved_at", sa.DateTime(), nullable=True))
    op.add_column("incident_dispatches", sa.Column("closed_at", sa.DateTime(), nullable=True))
    op.add_column(
        "incident_dispatches", sa.Column("acknowledged_by", sa.String(length=255), nullable=True)
    )
    op.add_column("incident_dispatches", sa.Column("resolution_note", sa.Text(), nullable=True))
    op.add_column(
        "incident_dispatches", sa.Column("resolution_proof_url", sa.String(length=512), nullable=True)
    )
    op.add_column(
        "incident_dispatches", sa.Column("last_status_update_at", sa.DateTime(), nullable=True)
    )
    op.add_column("incident_dispatches", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.add_column("incident_dispatches", sa.Column("updated_at", sa.DateTime(), nullable=True))

    op.execute(
        """
        UPDATE incident_dispatches
        SET
            status = CASE
                WHEN ack_status = 'acknowledged' THEN 'acknowledged'
                WHEN delivery_status = 'failed' THEN 'failed'
                WHEN delivery_status = 'delivered' THEN 'delivered'
                WHEN delivery_status = 'sent' THEN 'sent'
                ELSE 'pending'
            END,
            delivered_at = delivery_confirmed_at,
            created_at = COALESCE(dispatched_at, CURRENT_TIMESTAMP),
            updated_at = COALESCE(ack_at, delivery_confirmed_at, dispatched_at, CURRENT_TIMESTAMP),
            last_status_update_at = COALESCE(ack_at, delivery_confirmed_at, dispatched_at, CURRENT_TIMESTAMP)
        """
    )

    op.alter_column("incident_dispatches", "status", nullable=False, server_default="pending")
    op.alter_column(
        "incident_dispatches",
        "created_at",
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "incident_dispatches",
        "updated_at",
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    op.create_index("ix_incident_dispatches_status", "incident_dispatches", ["status"], unique=False)


def downgrade():
    op.drop_index("ix_incident_dispatches_status", table_name="incident_dispatches")
    op.drop_column("incident_dispatches", "updated_at")
    op.drop_column("incident_dispatches", "created_at")
    op.drop_column("incident_dispatches", "last_status_update_at")
    op.drop_column("incident_dispatches", "resolution_proof_url")
    op.drop_column("incident_dispatches", "resolution_note")
    op.drop_column("incident_dispatches", "acknowledged_by")
    op.drop_column("incident_dispatches", "closed_at")
    op.drop_column("incident_dispatches", "resolved_at")
    op.drop_column("incident_dispatches", "delivered_at")
    op.drop_column("incident_dispatches", "external_reference_source")
    op.drop_column("incident_dispatches", "external_reference_number")
    op.drop_column("incident_dispatches", "failure_reason")
    op.drop_column("incident_dispatches", "delivery_reference")
    op.drop_column("incident_dispatches", "delivery_provider")
    op.drop_column("incident_dispatches", "message_snapshot")
    op.drop_column("incident_dispatches", "subject_snapshot")
    op.drop_column("incident_dispatches", "recipient_email")
    op.drop_column("incident_dispatches", "status")
