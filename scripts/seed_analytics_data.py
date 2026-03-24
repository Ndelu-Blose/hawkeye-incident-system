"""Seed a larger dataset for analytics performance validation (Phase 4C).

Creates ~1,500 incidents with full event ledger, ownership, and audit entries.
Run with: python scripts/seed_analytics_data.py [count]

Requires: FLASK_APP=app, database configured.
For testing: pass app from fixture so seed uses the same DB.
"""

from __future__ import annotations

import os
import random
import sys
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import create_app
from app.constants import IncidentEventType, IncidentStatus, Roles
from app.extensions import db
from app.models.audit_log import AuditLog
from app.models.authority import Authority
from app.models.incident import Incident
from app.models.incident_assignment import IncidentAssignment
from app.models.incident_category import IncidentCategory
from app.models.incident_dispatch import IncidentDispatch
from app.models.incident_event import IncidentEvent
from app.models.incident_ownership_history import IncidentOwnershipHistory
from app.models.user import User
from app.services.auth_service import auth_service

if TYPE_CHECKING:
    from flask import Flask


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _get_or_create_category(name: str, description: str = "", **kwargs: object) -> IncidentCategory:
    """Get existing category by name or create if missing. Idempotent for lookup data."""
    cat = IncidentCategory.query.filter_by(name=name).first()
    if cat:
        return cat
    cat = IncidentCategory(name=name, description=description or name.title(), **kwargs)
    db.session.add(cat)
    db.session.flush()
    return cat


def _get_or_create_authority(name: str, **kwargs: object) -> Authority:
    """Get existing authority by name or create if missing. Idempotent for lookup data."""
    auth = Authority.query.filter_by(name=name).first()
    if auth:
        return auth
    auth = Authority(name=name, **kwargs)
    db.session.add(auth)
    db.session.flush()
    return auth


def _get_or_create_user(email: str, name: str, password: str, role: str) -> User:
    """Get existing user by email or create if missing. Idempotent for seed users."""
    user = auth_service.user_repo.get_by_email(email)
    if user:
        return user
    user, errors = auth_service.register_user(name=name, email=email, password=password, role=role)
    if user is None:
        raise RuntimeError(f"Failed to create user {email}: {errors}")
    return user


def seed(count: int = 1500, app: Flask | None = None) -> None:
    """Seed incidents with events, ownership, and audit entries.

    Reference data (categories, authorities, seed users) is resolved with get-or-create
    so the script is idempotent and safe to run multiple times.
    If app is provided (e.g. from a test fixture), use its context.
    Otherwise create app from FLASK_CONFIG / development.
    """
    if app is None:
        app = create_app()
    with app.app_context():
        resident = _get_or_create_user(
            email="seed-resident@example.com",
            name="Seed Resident",
            password="seedpass",
            role=Roles.RESIDENT.value,
        )
        admin = _get_or_create_user(
            email="seed-admin@example.com",
            name="Seed Admin",
            password="seedpass",
            role=Roles.ADMIN.value,
        )

        auth = _get_or_create_authority(name="Water Dept", is_active=True)
        category_names = ["pothole", "streetlight", "dumping", "noise", "other"]
        category_objs: list[IncidentCategory] = []
        for name in category_names:
            cat = _get_or_create_category(name=name, description=name.title(), is_active=True)
            category_objs.append(cat)
        db.session.commit()

        suburbs = ["North", "South", "East", "West", "Central"] * 20
        categories = category_names
        statuses = [
            IncidentStatus.REPORTED,
            IncidentStatus.SCREENED,
            IncidentStatus.ASSIGNED,
            IncidentStatus.ACKNOWLEDGED,
            IncidentStatus.IN_PROGRESS,
            IncidentStatus.RESOLVED,
            IncidentStatus.CLOSED,
            IncidentStatus.REJECTED,
        ]
        # Weight toward resolved/closed for resolution-time analytics (index -> weight)
        status_weights = [5, 5, 8, 8, 10, 25, 25, 4]
        weighted_pool: list[IncidentStatus] = []
        for s, w in zip(statuses, status_weights, strict=True):
            weighted_pool.extend([s] * w)

        base = _utc_now() - timedelta(days=30)
        ref_base = random.randint(
            900000, 999999 - count
        )  # unique per run to avoid ref_code collision
        created_count = 0

        for i in range(count):
            day_offset = i % 30
            reported_at = base + timedelta(days=day_offset, hours=i % 24, minutes=i % 60)
            suburb = suburbs[i % len(suburbs)]
            cat_idx = i % len(category_objs)
            cat_obj = category_objs[cat_idx]
            category_name = categories[cat_idx]
            status = weighted_pool[i % len(weighted_pool)]

            incident = Incident(
                reported_by_id=resident.id,
                title=f"Seed incident {i}",
                description="Seeded for analytics validation",
                category=category_name,
                category_id=cat_obj.id,
                suburb_or_ward=suburb,
                street_or_landmark="Main St",
                location=f"Main St, {suburb}",
                severity="low",
                status=status.value,
                reference_code=f"HK-2026-03-{ref_base + i:06d}",
                reported_at=reported_at,
                current_authority_id=auth.id if status != IncidentStatus.REPORTED else None,
            )
            if status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
                incident.resolved_at = reported_at + timedelta(hours=12 + (i % 48))
            db.session.add(incident)
            db.session.flush()

            # incident_created event
            db.session.add(
                IncidentEvent(
                    incident_id=incident.id,
                    event_type=IncidentEventType.INCIDENT_CREATED.value,
                    to_status=IncidentStatus.REPORTED.value,
                    actor_user_id=resident.id,
                    actor_role="resident",
                    created_at=reported_at,
                )
            )

            if status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
                db.session.add(
                    IncidentEvent(
                        incident_id=incident.id,
                        event_type=IncidentEventType.INCIDENT_RESOLVED.value,
                        from_status=IncidentStatus.IN_PROGRESS.value,
                        to_status=IncidentStatus.RESOLVED.value,
                        actor_user_id=admin.id,
                        actor_role="admin",
                        created_at=incident.resolved_at,
                    )
                )

            if status == IncidentStatus.REJECTED:
                db.session.add(
                    IncidentEvent(
                        incident_id=incident.id,
                        event_type=IncidentEventType.INCIDENT_REJECTED.value,
                        from_status=IncidentStatus.REPORTED.value,
                        to_status=IncidentStatus.REJECTED.value,
                        actor_user_id=admin.id,
                        actor_role="admin",
                        reason="Duplicate",
                        created_at=reported_at + timedelta(hours=2),
                    )
                )

            if status not in (IncidentStatus.REPORTED, IncidentStatus.REJECTED):
                assignment = IncidentAssignment(
                    incident_id=incident.id,
                    authority_id=auth.id,
                    assigned_by_user_id=admin.id,
                )
                db.session.add(assignment)
                db.session.flush()
                dispatch = IncidentDispatch(
                    incident_assignment_id=assignment.id,
                    incident_id=incident.id,
                    authority_id=auth.id,
                    dispatched_by_type="admin",
                    dispatched_by_id=admin.id,
                    ack_status="acknowledged" if status != IncidentStatus.ASSIGNED else "pending",
                    ack_at=reported_at + timedelta(hours=1)
                    if status != IncidentStatus.ASSIGNED
                    else None,
                )
                db.session.add(dispatch)
                db.session.flush()

                db.session.add(
                    IncidentOwnershipHistory(
                        incident_id=incident.id,
                        authority_id=auth.id,
                        assigned_by_user_id=admin.id,
                        is_current=(
                            status
                            in (
                                IncidentStatus.ASSIGNED,
                                IncidentStatus.ACKNOWLEDGED,
                                IncidentStatus.IN_PROGRESS,
                            )
                        ),
                        ended_at=reported_at + timedelta(hours=12)
                        if status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED)
                        else None,
                        dispatch_id=dispatch.id,
                    )
                )

            if i % 50 == 0 and status == IncidentStatus.CLOSED:
                db.session.add(
                    AuditLog(
                        entity_type="incident",
                        entity_id=incident.id,
                        action="incident_status_override",
                        actor_user_id=admin.id,
                        actor_role="admin",
                        reason="Test override",
                        before_json={"status": "resolved"},
                        after_json={"status": "closed"},
                        created_at=reported_at + timedelta(hours=24),
                    )
                )

            created_count += 1
            if created_count % 100 == 0:
                db.session.commit()
                print(f"  ... {created_count} incidents")

        db.session.commit()
        print(f"Seeded {created_count} incidents with events, ownership, and audit entries.")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    seed(n)
