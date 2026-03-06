"""Civic support tables: profiles, locations, categories, authorities, routing.

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b3c4d5e6f7a8"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    # locations first (resident_profiles and routing_rules reference it)
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("province", sa.String(length=100), nullable=True),
        sa.Column("municipality", sa.String(length=150), nullable=True),
        sa.Column("district", sa.String(length=150), nullable=True),
        sa.Column("ward", sa.String(length=50), nullable=True),
        sa.Column("suburb", sa.String(length=150), nullable=True),
        sa.Column("area_name", sa.String(length=255), nullable=True),
        sa.Column("boundary_geojson", sa.Text(), nullable=True),
        sa.Column("parent_location_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["parent_location_id"],
            ["locations.id"],
            ondelete="SET NULL",
        ),
    )
    with op.batch_alter_table("locations", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_locations_municipality"),
            ["municipality"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_locations_district"),
            ["district"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_locations_ward"),
            ["ward"],
            unique=False,
        )

    # authorities
    op.create_table(
        "authorities",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("authority_type", sa.String(length=50), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=50), nullable=True),
        sa.Column("jurisdiction_notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # incident_categories
    op.create_table(
        "incident_categories",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("department_hint", sa.String(length=150), nullable=True),
        sa.Column("default_priority", sa.String(length=32), nullable=True),
        sa.Column("default_sla_hours", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    with op.batch_alter_table("incident_categories", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_incident_categories_name"),
            ["name"],
            unique=True,
        )

    # resident_profiles (references locations)
    op.create_table(
        "resident_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("phone_number", sa.String(length=32), nullable=True),
        sa.Column("street_address_1", sa.String(length=255), nullable=True),
        sa.Column("street_address_2", sa.String(length=255), nullable=True),
        sa.Column("suburb", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("municipality_id", sa.Integer(), nullable=True),
        sa.Column("district_id", sa.Integer(), nullable=True),
        sa.Column("ward_id", sa.Integer(), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("location_verified", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("profile_completed", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("consent_location", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["municipality_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["district_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["ward_id"], ["locations.id"]),
    )
    with op.batch_alter_table("resident_profiles", schema=None) as batch_op:
        batch_op.create_unique_constraint("uq_resident_profiles_user_id", ["user_id"])
        batch_op.create_index(
            batch_op.f("ix_resident_profiles_user_id"),
            ["user_id"],
            unique=False,
        )

    # authority_users (join between users and authorities)
    op.create_table(
        "authority_users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("authority_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_title", sa.String(length=120), nullable=True),
        sa.Column("can_assign", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("can_resolve", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("can_export", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["authority_id"], ["authorities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    with op.batch_alter_table("authority_users", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_authority_users_authority_id"),
            ["authority_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_authority_users_user_id"),
            ["user_id"],
            unique=False,
        )
        batch_op.create_unique_constraint(
            "uq_authority_users_authority_user",
            ["authority_id", "user_id"],
        )

    # incident_assignments
    op.create_table(
        "incident_assignments",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("authority_id", sa.Integer(), nullable=False),
        sa.Column("assigned_to_user_id", sa.Integer(), nullable=True),
        sa.Column("assigned_by_user_id", sa.Integer(), nullable=True),
        sa.Column("assignment_reason", sa.Text(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column("unassigned_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["authority_id"], ["authorities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["assigned_to_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
    )
    with op.batch_alter_table("incident_assignments", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_incident_assignments_incident_id"),
            ["incident_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_incident_assignments_authority_id"),
            ["authority_id"],
            unique=False,
        )

    # routing_rules
    op.create_table(
        "routing_rules",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("authority_id", sa.Integer(), nullable=False),
        sa.Column("priority_override", sa.String(length=32), nullable=True),
        sa.Column("sla_hours_override", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["incident_categories.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["authority_id"],
            ["authorities.id"],
            ondelete="CASCADE",
        ),
    )
    with op.batch_alter_table("routing_rules", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_routing_rules_category_id"),
            ["category_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_routing_rules_location_id"),
            ["location_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_routing_rules_authority_id"),
            ["authority_id"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("routing_rules", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_routing_rules_authority_id"))
        batch_op.drop_index(batch_op.f("ix_routing_rules_location_id"))
        batch_op.drop_index(batch_op.f("ix_routing_rules_category_id"))
    op.drop_table("routing_rules")

    with op.batch_alter_table("incident_assignments", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_incident_assignments_authority_id"))
        batch_op.drop_index(batch_op.f("ix_incident_assignments_incident_id"))
    op.drop_table("incident_assignments")

    with op.batch_alter_table("authority_users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_authority_users_user_id"))
        batch_op.drop_index(batch_op.f("ix_authority_users_authority_id"))
        batch_op.drop_constraint(
            "uq_authority_users_authority_user",
            type_="unique",
        )
    op.drop_table("authority_users")

    with op.batch_alter_table("incident_categories", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_incident_categories_name"))
    op.drop_table("incident_categories")

    with op.batch_alter_table("resident_profiles", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_resident_profiles_user_id"))
        batch_op.drop_constraint(
            "uq_resident_profiles_user_id",
            type_="unique",
        )
    op.drop_table("resident_profiles")

    op.drop_table("authorities")

    with op.batch_alter_table("locations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_locations_ward"))
        batch_op.drop_index(batch_op.f("ix_locations_district"))
        batch_op.drop_index(batch_op.f("ix_locations_municipality"))
    op.drop_table("locations")

