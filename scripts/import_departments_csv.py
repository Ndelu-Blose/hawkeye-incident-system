"""Import production departments from CSV with idempotent upsert.

Run:
    python scripts/import_departments_csv.py
"""

from __future__ import annotations

import csv
import os
import re
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import create_app
from app.extensions import db
from app.models import Authority, DepartmentContact

CSV_PATH = os.path.join(ROOT_DIR, "scripts", "data", "production_departments.csv")


def _slugify(value: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower())
    return token.strip("-")


def _to_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y"}


def import_departments_csv(path: str = CSV_PATH) -> tuple[int, int]:
    departments_created = 0
    contacts_created = 0
    rows_by_department: dict[str, list[dict[str, str]]] = {}

    with open(path, encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            code = (row.get("department_code") or "").strip().upper()
            if not code:
                continue
            rows_by_department.setdefault(code, []).append(row)

    for code, rows in rows_by_department.items():
        first = rows[0]
        name = (first.get("name") or "").strip()
        operating_hours = (first.get("operating_hours") or "").strip() or None
        physical_address = (first.get("physical_address") or "").strip() or None
        service_hub = (first.get("service_hub") or "").strip() or None
        authority = (
            Authority.query.filter(Authority.code == code).first()
            or Authority.query.filter(Authority.name == name).first()
        )
        if authority is None:
            authority = Authority(
                code=code,
                name=name,
                slug=_slugify(name),
                is_active=True,
                routing_enabled=True,
                notifications_enabled=True,
            )
            db.session.add(authority)
            db.session.flush()
            departments_created += 1

        authority.name = name
        authority.code = code
        authority.slug = authority.slug or _slugify(name)
        authority.is_active = True
        authority.routing_enabled = True
        authority.notifications_enabled = True
        authority.operating_hours = operating_hours
        authority.physical_address = physical_address
        authority.service_hub = service_hub

        known_keys: set[tuple[str, str, str]] = set()
        for row in rows:
            channel = (row.get("channel") or "").strip().lower()
            contact_type = (row.get("type") or "primary").strip().lower()
            value = (row.get("value") or "").strip()
            if not channel or not value:
                continue
            key = (contact_type, channel, value)
            known_keys.add(key)
            existing = DepartmentContact.query.filter(
                DepartmentContact.authority_id == authority.id,
                DepartmentContact.contact_type == contact_type,
                DepartmentContact.channel == channel,
                DepartmentContact.value == value,
            ).first()
            is_primary = contact_type == "primary"
            is_secondary = contact_type == "secondary"
            verification_status = (row.get("verification_status") or "unverified").strip().lower()
            source_url = (row.get("source_url") or "").strip() or None
            notes = (row.get("notes") or "").strip() or None
            after_hours = _to_bool(row.get("after_hours"))

            if existing is None:
                db.session.add(
                    DepartmentContact(
                        authority_id=authority.id,
                        contact_type=contact_type,
                        channel=channel,
                        value=value,
                        is_primary=is_primary,
                        is_secondary=is_secondary,
                        verification_status=verification_status,
                        source_url=source_url,
                        notes=notes,
                        after_hours=after_hours,
                        is_active=True,
                    )
                )
                contacts_created += 1
                continue

            existing.is_active = True
            existing.is_primary = is_primary
            existing.is_secondary = is_secondary
            existing.verification_status = verification_status
            existing.source_url = source_url
            existing.notes = notes
            existing.after_hours = after_hours

        for existing in DepartmentContact.query.filter(
            DepartmentContact.authority_id == authority.id
        ).all():
            existing.is_active = (
                existing.contact_type,
                existing.channel,
                existing.value,
            ) in known_keys

    db.session.commit()
    return departments_created, contacts_created


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        created_departments, created_contacts = import_departments_csv()
        print(f"Departments created: {created_departments}")
        print(f"Contacts created: {created_contacts}")
