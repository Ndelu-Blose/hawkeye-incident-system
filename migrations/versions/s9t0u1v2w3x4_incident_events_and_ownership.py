"""Add incident_events and incident_ownership_history tables.

Revision ID: s9t0u1v2w3x4
Revises: j2k3l4m5n6o7
Create Date: 2026-03-11

Sprint 1: Canonical event ledger and ownership history.
"""
from alembic import op
import sqlalchemy as sa


revision = "s9t0u1v2w3x4"
down_revision = "j2k3l4m5n6o7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "incident_events",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "incident_id",
            sa.Integer(),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=True),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_role", sa.String(length=32), nullable=True),
        sa.Column(
            "authority_id",
            sa.Integer(),
            sa.ForeignKey("authorities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "dispatch_id",
            sa.Integer(),
            sa.ForeignKey("incident_dispatches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_incident_events_incident_id",
        "incident_events",
        ["incident_id"],
        unique=False,
    )
    op.create_index(
        "ix_incident_events_event_type",
        "incident_events",
        ["event_type"],
        unique=False,
    )

    op.create_table(
        "incident_ownership_history",
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
            "assigned_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "dispatch_id",
            sa.Integer(),
            sa.ForeignKey("incident_dispatches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_incident_ownership_history_incident_id",
        "incident_ownership_history",
        ["incident_id"],
        unique=False,
    )
    # Partial unique index: exactly one current ownership row per incident (PostgreSQL only)
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(
            """
            CREATE UNIQUE INDEX ix_incident_ownership_history_incident_current
            ON incident_ownership_history (incident_id)
            WHERE is_current = true
            """
        )


def downgrade():
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.drop_index(
            "ix_incident_ownership_history_incident_current",
            table_name="incident_ownership_history",
        )
    op.drop_index(
        "ix_incident_ownership_history_incident_id",
        table_name="incident_ownership_history",
    )
    op.drop_table("incident_ownership_history")
    op.drop_index("ix_incident_events_event_type", table_name="incident_events")
    op.drop_index("ix_incident_events_incident_id", table_name="incident_events")
    op.drop_table("incident_events")
