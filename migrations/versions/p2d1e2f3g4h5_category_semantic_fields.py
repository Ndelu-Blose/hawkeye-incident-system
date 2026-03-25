"""Add canonical incident category semantic fields.

Revision ID: p2d1e2f3g4h5
Revises: p2c1d2e3f4g5
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "p2d1e2f3g4h5"
down_revision = "p2c1d2e3f4g5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("incidents", schema=None) as batch_op:
        batch_op.add_column(sa.Column("reported_category_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("final_category_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_incidents_reported_category_id_incident_categories",
            "incident_categories",
            ["reported_category_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_incidents_final_category_id_incident_categories",
            "incident_categories",
            ["final_category_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            batch_op.f("ix_incidents_reported_category_id"),
            ["reported_category_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_incidents_final_category_id"),
            ["final_category_id"],
            unique=False,
        )

    op.execute(
        sa.text(
            """
            UPDATE incidents
            SET reported_category_id = COALESCE(resident_category_id, category_id)
            WHERE reported_category_id IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE incidents
            SET final_category_id = COALESCE(system_category_id, category_id)
            WHERE final_category_id IS NULL
            """
        )
    )


def downgrade():
    with op.batch_alter_table("incidents", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_incidents_final_category_id"))
        batch_op.drop_index(batch_op.f("ix_incidents_reported_category_id"))
        batch_op.drop_constraint(
            "fk_incidents_final_category_id_incident_categories",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_incidents_reported_category_id_incident_categories",
            type_="foreignkey",
        )
        batch_op.drop_column("final_category_id")
        batch_op.drop_column("reported_category_id")
