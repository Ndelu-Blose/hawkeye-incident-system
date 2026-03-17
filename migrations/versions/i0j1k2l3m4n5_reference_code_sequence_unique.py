"""Reference code: sequence, rename to reference_code, backfill, unique constraint.

Revision ID: i0j1k2l3m4n5
Revises: 198053cb6a01
Create Date: 2026-03-11

Implements:
- PostgreSQL sequence incident_ref_seq for atomic reference code generation
- Rename incidents.reference_no -> reference_code (align with v3 plan)
- Backfill NULL/empty reference_code using sequence + created_at (HK-YYYY-MM-NNNNNN)
- NOT NULL and UNIQUE constraint on reference_code
"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "i0j1k2l3m4n5"
down_revision = "198053cb6a01"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # 1. Create sequence (safe to run even if it exists)
    op.execute(
        "CREATE SEQUENCE IF NOT EXISTS incident_ref_seq "
        "START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1"
    )

    # 2. Set sequence start above highest existing HK-YYYY-MM-NNNNNN code
    #    (column still named reference_no at this point)
    result = conn.execute(
        text(
            "SELECT COALESCE(MAX(CAST(NULLIF(TRIM(SPLIT_PART(reference_no, '-', 4)), '') AS INTEGER)), 0) + 1 "
            "FROM incidents "
            "WHERE reference_no IS NOT NULL AND reference_no ~ '^HK-[0-9]{4}-[0-9]{2}-[0-9]+$'"
        )
    ).scalar()
    start_val = result if result is not None else 1
    conn.execute(text("SELECT setval('incident_ref_seq', :v)"), {"v": start_val})

    # 3. Rename column
    op.execute("ALTER TABLE incidents RENAME COLUMN reference_no TO reference_code")

    # 4. Backfill NULL/empty using sequence and created_at
    op.execute(
        """
        UPDATE incidents
        SET reference_code = (
            'HK-' ||
            TO_CHAR(COALESCE(created_at, NOW()), 'YYYY') || '-' ||
            TO_CHAR(COALESCE(created_at, NOW()), 'MM') || '-' ||
            LPAD(CAST(nextval('incident_ref_seq') AS TEXT), 6, '0')
        )
        WHERE reference_code IS NULL OR TRIM(reference_code) = ''
        """
    )

    # 5. NOT NULL
    op.execute("ALTER TABLE incidents ALTER COLUMN reference_code SET NOT NULL")

    # 6. Drop old unique index (from extend migration) so we can add named constraint
    op.drop_index("ix_incidents_reference_no", table_name="incidents")

    # 7. Add named UNIQUE constraint
    op.create_unique_constraint(
        "uq_incidents_reference_code",
        "incidents",
        ["reference_code"],
    )


def downgrade():
    op.drop_constraint("uq_incidents_reference_code", "incidents", type_="unique")
    op.create_index(
        "ix_incidents_reference_no",
        "incidents",
        ["reference_code"],
        unique=True,
    )
    op.execute("ALTER TABLE incidents ALTER COLUMN reference_code DROP NOT NULL")
    op.execute("ALTER TABLE incidents RENAME COLUMN reference_code TO reference_no")
    op.execute("DROP SEQUENCE IF EXISTS incident_ref_seq")
