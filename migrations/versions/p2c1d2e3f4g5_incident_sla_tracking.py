"""Add incident SLA tracking backbone.

Revision ID: p2c1d2e3f4g5
Revises: p2b1c2d3e4f5
Create Date: 2026-03-25
"""

from datetime import UTC, datetime, timedelta

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "p2c1d2e3f4g5"
down_revision = "p2b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "incident_sla_tracking",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("sla_hours", sa.Integer(), nullable=False, server_default="72"),
        sa.Column("deadline_at", sa.DateTime(), nullable=False),
        sa.Column("breached_at", sa.DateTime(), nullable=True),
        sa.Column("warning_sent_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("incident_id", name="uq_incident_sla_tracking_incident_id"),
    )
    with op.batch_alter_table("incident_sla_tracking", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_incident_sla_tracking_incident_id"),
            ["incident_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_incident_sla_tracking_status"),
            ["status"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_incident_sla_tracking_deadline_at"),
            ["deadline_at"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_incident_sla_tracking_breached_at"),
            ["breached_at"],
            unique=False,
        )

    bind = op.get_bind()
    incidents = sa.table(
        "incidents",
        sa.column("id", sa.Integer()),
        sa.column("category_id", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("reported_at", sa.DateTime()),
        sa.column("created_at", sa.DateTime()),
    )
    categories = sa.table(
        "incident_categories",
        sa.column("id", sa.Integer()),
        sa.column("default_sla_hours", sa.Integer()),
    )
    sla_table = sa.table(
        "incident_sla_tracking",
        sa.column("incident_id", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("sla_hours", sa.Integer()),
        sa.column("deadline_at", sa.DateTime()),
        sa.column("breached_at", sa.DateTime()),
        sa.column("warning_sent_at", sa.DateTime()),
        sa.column("closed_at", sa.DateTime()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )

    rows = bind.execute(
        sa.select(
            incidents.c.id,
            incidents.c.status,
            incidents.c.reported_at,
            incidents.c.created_at,
            categories.c.default_sla_hours,
        ).select_from(
            incidents.outerjoin(categories, incidents.c.category_id == categories.c.id)
        )
    ).fetchall()

    now = datetime.now(UTC).replace(tzinfo=None)
    closed_statuses = {"resolved", "rejected", "closed"}
    inserts = []
    for row in rows:
        started_at = row.reported_at or row.created_at or now
        sla_hours = int(row.default_sla_hours or 72)
        deadline_at = started_at + timedelta(hours=sla_hours)
        is_closed = (row.status or "").strip().lower() in closed_statuses
        is_breached = (not is_closed) and deadline_at <= now
        inserts.append(
            {
                "incident_id": row.id,
                "status": "closed" if is_closed else ("breached" if is_breached else "open"),
                "sla_hours": sla_hours,
                "deadline_at": deadline_at,
                "breached_at": now if is_breached else None,
                "warning_sent_at": None,
                "closed_at": now if is_closed else None,
                "created_at": now,
                "updated_at": now,
            }
        )

    if inserts:
        op.bulk_insert(sla_table, inserts)


def downgrade():
    with op.batch_alter_table("incident_sla_tracking", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_incident_sla_tracking_breached_at"))
        batch_op.drop_index(batch_op.f("ix_incident_sla_tracking_deadline_at"))
        batch_op.drop_index(batch_op.f("ix_incident_sla_tracking_status"))
        batch_op.drop_index(batch_op.f("ix_incident_sla_tracking_incident_id"))
    op.drop_table("incident_sla_tracking")
