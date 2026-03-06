"""Seed incident_categories, one authority, and default routing_rules.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-03-06

"""
from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None

CATEGORIES = [
    ("pothole", "Road surface damage", "Roads", "medium", 72),
    ("broken_streetlight", "Non-working street light", "Electricity", "medium", 48),
    ("dumping", "Illegal dumping", "Waste", "low", 168),
    ("crime", "Criminal activity", "Safety", "critical", 4),
    ("vandalism", "Vandalism or damage", "Safety", "high", 24),
    ("water_leak", "Water leak or burst", "Water", "high", 12),
    ("blocked_drain", "Blocked drain", "Water", "medium", 48),
    ("suspicious_activity", "Suspicious activity", "Safety", "high", 8),
]


def upgrade():
    conn = op.get_bind()
    for name, description, dept, priority, sla in CATEGORIES:
        conn.execute(
            text(
                """
                INSERT INTO incident_categories
                (name, description, department_hint, default_priority, default_sla_hours, is_active, created_at, updated_at)
                VALUES (:name, :description, :dept, :priority, :sla, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (name) DO NOTHING
                """
            ),
            {
                "name": name,
                "description": description,
                "dept": dept,
                "priority": priority,
                "sla": sla,
            },
        )

    conn.execute(
        text(
            """
            INSERT INTO authorities (name, authority_type, is_active, created_at, updated_at)
            SELECT 'Municipal Operations', 'municipality', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            WHERE NOT EXISTS (SELECT 1 FROM authorities WHERE name = 'Municipal Operations')
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO routing_rules (category_id, authority_id, is_active, created_at, updated_at)
            SELECT c.id, (SELECT id FROM authorities WHERE name = 'Municipal Operations' LIMIT 1), true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM incident_categories c
            WHERE NOT EXISTS (SELECT 1 FROM routing_rules r WHERE r.category_id = c.id AND r.location_id IS NULL)
            """
        )
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        text(
            "DELETE FROM routing_rules WHERE authority_id IN (SELECT id FROM authorities WHERE name = 'Municipal Operations')"
        )
    )
    conn.execute(
        text("DELETE FROM authorities WHERE name = 'Municipal Operations'")
    )
    for name, _, _, _, _ in CATEGORIES:
        conn.execute(text("DELETE FROM incident_categories WHERE name = :name"), {"name": name})
