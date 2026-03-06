"""Extend users and incidents with verification, GIS, routing, and SLA fields.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-03-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c4d5e6f7a8b9"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade():
    # Extend users with activation / verification fields
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("TRUE"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "email_verified",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("FALSE"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "phone_verified",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("FALSE"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "last_login_at",
                sa.DateTime(),
                nullable=True,
            )
        )

    # Extend incidents with GIS, routing, and SLA fields
    with op.batch_alter_table("incidents", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("reference_no", sa.String(length=32), nullable=True)
        )
        batch_op.add_column(
            sa.Column("resident_profile_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("category_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("location_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("latitude", sa.Numeric(9, 6), nullable=True)
        )
        batch_op.add_column(
            sa.Column("longitude", sa.Numeric(9, 6), nullable=True)
        )
        batch_op.add_column(
            sa.Column("current_authority_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "is_anonymous",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("FALSE"),
            )
        )
        batch_op.add_column(
            sa.Column("duplicate_of_incident_id", sa.Integer(), nullable=True)
        )

        batch_op.add_column(
            sa.Column("reported_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("acknowledged_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("assigned_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("resolved_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("closed_at", sa.DateTime(), nullable=True)
        )

        batch_op.create_index(
            batch_op.f("ix_incidents_reference_no"),
            ["reference_no"],
            unique=True,
        )
        batch_op.create_index(
            batch_op.f("ix_incidents_location_id"),
            ["location_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_incidents_current_authority_id"),
            ["current_authority_id"],
            unique=False,
        )

        batch_op.create_foreign_key(
            "fk_incidents_resident_profile_id_resident_profiles",
            "resident_profiles",
            ["resident_profile_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_incidents_category_id_incident_categories",
            "incident_categories",
            ["category_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_incidents_location_id_locations",
            "locations",
            ["location_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_incidents_current_authority_id_authorities",
            "authorities",
            ["current_authority_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_incidents_duplicate_of_incident_id_incidents",
            "incidents",
            ["duplicate_of_incident_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade():
    with op.batch_alter_table("incidents", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_incidents_duplicate_of_incident_id_incidents",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_incidents_current_authority_id_authorities",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_incidents_location_id_locations",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_incidents_category_id_incident_categories",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_incidents_resident_profile_id_resident_profiles",
            type_="foreignkey",
        )

        batch_op.drop_index(batch_op.f("ix_incidents_current_authority_id"))
        batch_op.drop_index(batch_op.f("ix_incidents_location_id"))
        batch_op.drop_index(batch_op.f("ix_incidents_reference_no"))

        batch_op.drop_column("closed_at")
        batch_op.drop_column("resolved_at")
        batch_op.drop_column("assigned_at")
        batch_op.drop_column("acknowledged_at")
        batch_op.drop_column("reported_at")
        batch_op.drop_column("duplicate_of_incident_id")
        batch_op.drop_column("is_anonymous")
        batch_op.drop_column("current_authority_id")
        batch_op.drop_column("longitude")
        batch_op.drop_column("latitude")
        batch_op.drop_column("location_id")
        batch_op.drop_column("category_id")
        batch_op.drop_column("resident_profile_id")
        batch_op.drop_column("reference_no")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("last_login_at")
        batch_op.drop_column("phone_verified")
        batch_op.drop_column("email_verified")
        batch_op.drop_column("is_active")

