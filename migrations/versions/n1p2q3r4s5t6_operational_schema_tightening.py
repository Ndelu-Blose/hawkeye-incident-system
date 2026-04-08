"""Operational schema tightening for routing and auditability.

Revision ID: n1p2q3r4s5t6
Revises: 6ff356fa4d02
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "n1p2q3r4s5t6"
down_revision = "6ff356fa4d02"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("locations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("location_type", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("name", sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column("code", sa.String(length=64), nullable=True))
        batch_op.create_index(batch_op.f("ix_locations_location_type"), ["location_type"], unique=False)
        batch_op.create_index(batch_op.f("ix_locations_name"), ["name"], unique=False)
        batch_op.create_index(batch_op.f("ix_locations_code"), ["code"], unique=False)
        batch_op.create_unique_constraint("uq_locations_code", ["code"])

    op.execute(
        sa.text(
            """
            UPDATE locations
            SET name = COALESCE(area_name, suburb, ward, municipality, district, province, country)
            WHERE name IS NULL
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE locations
            SET location_type = CASE
                WHEN ward IS NOT NULL THEN 'ward'
                WHEN suburb IS NOT NULL THEN 'suburb'
                WHEN municipality IS NOT NULL THEN 'municipality'
                WHEN district IS NOT NULL THEN 'district'
                WHEN province IS NOT NULL THEN 'province'
                WHEN country IS NOT NULL THEN 'country'
                ELSE NULL
            END
            WHERE location_type IS NULL
            """
        )
    )

    with op.batch_alter_table("routing_rules", schema=None) as batch_op:
        batch_op.add_column(sa.Column("priority", sa.Integer(), nullable=False, server_default="100"))
        batch_op.add_column(sa.Column("effective_from", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("effective_to", sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f("ix_routing_rules_priority"), ["priority"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_routing_rules_effective_from"),
            ["effective_from"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_routing_rules_effective_to"),
            ["effective_to"],
            unique=False,
        )

    with op.batch_alter_table("incident_events", schema=None) as batch_op:
        batch_op.add_column(sa.Column("assignment_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_incident_events_assignment_id_incident_assignments",
            "incident_assignments",
            ["assignment_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(batch_op.f("ix_incident_events_assignment_id"), ["assignment_id"], unique=False)

    with op.batch_alter_table("incidents", schema=None) as batch_op:
        batch_op.add_column(sa.Column("duplicate_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("duplicate_confirmed_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("duplicate_confirmed_at", sa.DateTime(), nullable=True))
        batch_op.create_foreign_key(
            "fk_incidents_duplicate_confirmed_by_user_id_users",
            "users",
            ["duplicate_confirmed_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            batch_op.f("ix_incidents_duplicate_confirmed_by_user_id"),
            ["duplicate_confirmed_by_user_id"],
            unique=False,
        )

    with op.batch_alter_table("authority_users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("role_in_authority", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("is_primary_contact", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")))
        batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")))
        batch_op.add_column(sa.Column("joined_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
        batch_op.create_index(
            batch_op.f("ix_authority_users_is_primary_contact"),
            ["is_primary_contact"],
            unique=False,
        )
        batch_op.create_index(batch_op.f("ix_authority_users_is_active"), ["is_active"], unique=False)


def downgrade():
    with op.batch_alter_table("authority_users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_authority_users_is_active"))
        batch_op.drop_index(batch_op.f("ix_authority_users_is_primary_contact"))
        batch_op.drop_column("joined_at")
        batch_op.drop_column("is_active")
        batch_op.drop_column("is_primary_contact")
        batch_op.drop_column("role_in_authority")

    with op.batch_alter_table("incidents", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_incidents_duplicate_confirmed_by_user_id"))
        batch_op.drop_constraint("fk_incidents_duplicate_confirmed_by_user_id_users", type_="foreignkey")
        batch_op.drop_column("duplicate_confirmed_at")
        batch_op.drop_column("duplicate_confirmed_by_user_id")
        batch_op.drop_column("duplicate_reason")

    with op.batch_alter_table("incident_events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_incident_events_assignment_id"))
        batch_op.drop_constraint(
            "fk_incident_events_assignment_id_incident_assignments",
            type_="foreignkey",
        )
        batch_op.drop_column("assignment_id")

    with op.batch_alter_table("routing_rules", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_routing_rules_effective_to"))
        batch_op.drop_index(batch_op.f("ix_routing_rules_effective_from"))
        batch_op.drop_index(batch_op.f("ix_routing_rules_priority"))
        batch_op.drop_column("effective_to")
        batch_op.drop_column("effective_from")
        batch_op.drop_column("priority")

    with op.batch_alter_table("locations", schema=None) as batch_op:
        batch_op.drop_constraint("uq_locations_code", type_="unique")
        batch_op.drop_index(batch_op.f("ix_locations_code"))
        batch_op.drop_index(batch_op.f("ix_locations_name"))
        batch_op.drop_index(batch_op.f("ix_locations_location_type"))
        batch_op.drop_column("code")
        batch_op.drop_column("name")
        batch_op.drop_column("location_type")
