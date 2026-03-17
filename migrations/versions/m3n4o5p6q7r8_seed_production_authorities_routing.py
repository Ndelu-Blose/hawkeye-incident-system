"""Seed production authorities and category→authority routing rules.

Revision ID: m3n4o5p6q7r8
Revises: j2k3l4m5n6o7
Create Date: 2026-03-11

Production-ready municipal departments aligned with South African local government
responsibilities. Routing rules map incident categories to the correct authority.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "m3n4o5p6q7r8"
down_revision = "j2k3l4m5n6o7"
branch_labels = None
depends_on = None

# Production departments (authorities) - real-world municipal structure
AUTHORITIES = [
    ("SAPS", "saps", "public_safety", "Handles criminal activity, investigations, arrests, and public safety enforcement."),
    ("Metro Police", "metro-police", "public_safety", "Enforces traffic laws and municipal by-laws including illegal parking and disturbances."),
    ("Municipal Operations", "municipal-operations", "municipality", "Coordinates municipal services and handles escalations across departments."),
    ("Water and Sanitation", "water-and-sanitation", "utility", "Responsible for water supply, sewer systems, and sanitation infrastructure."),
    ("Electricity", "electricity", "utility", "Manages power supply, outages, and electrical infrastructure."),
    ("Roads and Stormwater", "roads-and-stormwater", "infrastructure", "Maintains roads, stormwater drainage, and traffic infrastructure."),
    ("Waste Management", "waste-management", "environment", "Handles waste collection, illegal dumping, and sanitation services."),
    ("Parks and Recreation", "parks-and-recreation", "community_services", "Maintains parks, recreational spaces, and public facilities."),
    ("Human Settlements", "human-settlements", "community_services", "Responsible for housing development and informal settlements."),
    ("Public Safety", "public-safety", "public_safety", "Coordinates general safety initiatives and community protection programs."),
    ("Fire and Emergency Services", "fire-and-emergency", "emergency", "Handles fires, rescue operations, and emergency response services."),
    ("Traffic and Transport", "traffic-and-transport", "transport", "Manages traffic systems, road flow, and transport services."),
    ("Environmental Health", "environmental-health", "environment", "Monitors public health, pollution, and environmental safety."),
    ("Building Control", "building-control", "infrastructure", "Oversees construction compliance and building regulations."),
    ("Sewer and Drainage", "sewer-and-drainage", "utility", "Handles sewer blockages and drainage systems."),
    ("Street Lighting", "street-lighting", "infrastructure", "Maintains street lights and public lighting infrastructure."),
    ("Customer Support / Call Centre", "customer-support", "administration", "Handles citizen queries and service requests."),
    ("Disaster Management", "disaster-management", "emergency", "Coordinates disaster response such as floods and storms."),
    ("Cemeteries and Crematoria", "cemeteries", "community_services", "Manages burial services and cemetery operations."),
    ("Fleet and Mechanical Services", "fleet-services", "administration", "Maintains municipal vehicles and operational equipment."),
    ("Community Services", "community-services", "community_services", "Provides social development and community programs."),
    ("Facilities Maintenance", "facilities-maintenance", "administration", "Maintains municipal buildings and infrastructure."),
]

# Category name → authority slug (incident_categories.name → authorities.slug)
CATEGORY_TO_AUTHORITY = {
    "water_leak": "water-and-sanitation",
    "blocked_drain": "sewer-and-drainage",
    "crime": "saps",
    "suspicious_activity": "saps",
    "pothole": "roads-and-stormwater",
    "broken_streetlight": "street-lighting",
    "dumping": "waste-management",
    "vandalism": "municipal-operations",
}


def upgrade():
    conn = op.get_bind()

    # 1. Add slug column to authorities
    op.add_column("authorities", sa.Column("slug", sa.String(120), nullable=True))
    op.create_index("ix_authorities_slug", "authorities", ["slug"], unique=True)

    # 2. Backfill slug for existing Municipal Operations
    conn.execute(
        text(
            """
            UPDATE authorities SET slug = 'municipal-operations', jurisdiction_notes = 'Coordinates municipal services and handles escalations across departments.'
            WHERE name = 'Municipal Operations' AND slug IS NULL
            """
        )
    )

    # 3. Insert new authorities (skip Municipal Operations - already exists)
    for name, slug, auth_type, description in AUTHORITIES:
        if slug == "municipal-operations":
            continue
        conn.execute(
            text(
                """
                INSERT INTO authorities (name, slug, authority_type, jurisdiction_notes, is_active, created_at, updated_at)
                SELECT :name, :slug, :auth_type, :description, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                WHERE NOT EXISTS (SELECT 1 FROM authorities WHERE slug = :slug)
                """
            ),
            {"name": name, "slug": slug, "auth_type": auth_type, "description": description},
        )

    # 4. Replace routing rules: delete old category-only rules, add new category→authority mappings
    conn.execute(text("DELETE FROM routing_rules"))

    for cat_name, auth_slug in CATEGORY_TO_AUTHORITY.items():
        conn.execute(
            text(
                """
                INSERT INTO routing_rules (category_id, authority_id, location_id, is_active, created_at, updated_at)
                SELECT c.id, a.id, NULL, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                FROM incident_categories c, authorities a
                WHERE c.name = :cat_name AND a.slug = :auth_slug
                """
            ),
            {"cat_name": cat_name, "auth_slug": auth_slug},
        )

    # 5. Fallback: any category without a rule gets Municipal Operations
    conn.execute(
        text(
            """
            INSERT INTO routing_rules (category_id, authority_id, location_id, is_active, created_at, updated_at)
            SELECT c.id, (SELECT id FROM authorities WHERE slug = 'municipal-operations' LIMIT 1), NULL, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM incident_categories c
            WHERE NOT EXISTS (SELECT 1 FROM routing_rules r WHERE r.category_id = c.id AND r.location_id IS NULL)
            """
        )
    )


def downgrade():
    conn = op.get_bind()

    # Restore single authority + default routing (as in f7a8b9c0d1e2)
    conn.execute(text("DELETE FROM routing_rules"))

    conn.execute(
        text(
            """
            INSERT INTO routing_rules (category_id, authority_id, location_id, is_active, created_at, updated_at)
            SELECT c.id, (SELECT id FROM authorities WHERE name = 'Municipal Operations' LIMIT 1), NULL, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM incident_categories c
            """
        )
    )

    # Remove authorities added by this migration (keep Municipal Operations)
    conn.execute(
        text(
            "DELETE FROM authorities WHERE slug IS NOT NULL AND slug != 'municipal-operations'"
        )
    )

    op.drop_index("ix_authorities_slug", table_name="authorities")
    op.drop_column("authorities", "slug")
