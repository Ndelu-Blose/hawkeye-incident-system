"""Seed production-ready departments and normalized contact channels.

Run:
    python scripts/seed_departments.py
"""

from __future__ import annotations

import json
import os
import re
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import create_app
from app.extensions import db
from app.models import Authority, DepartmentContact

SEED_PATH = os.path.join(ROOT_DIR, "scripts", "data", "production_departments.json")


def _slugify(value: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower())
    return token.strip("-")


def _load_seed_data(path: str = SEED_PATH) -> dict:
    with open(path, encoding="utf-8") as fp:
        return json.load(fp)


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def seed_departments(path: str = SEED_PATH) -> tuple[int, int]:
    payload = _load_seed_data(path)
    departments = payload.get("departments") or []
    seeded_departments = 0
    seeded_contacts = 0

    for item in departments:
        code = (item.get("code") or "").strip().upper()
        name = (item.get("name") or "").strip()
        if not code or not name:
            continue

        authority = Authority.query.filter(Authority.code == code).first()
        operating_hours = (item.get("operating_hours") or "").strip() or None
        physical_address = (item.get("physical_address") or "").strip() or None
        service_hub = (item.get("service_hub") or "").strip() or None
        if authority is None:
            authority = Authority(
                code=code,
                name=name,
                slug=_slugify(name),
                is_active=True,
                routing_enabled=True,
                notifications_enabled=True,
                operating_hours=operating_hours,
                physical_address=physical_address,
                service_hub=service_hub,
            )
            db.session.add(authority)
            db.session.flush()
            seeded_departments += 1
        else:
            authority.name = name
            authority.code = code
            authority.slug = authority.slug or _slugify(name)
            authority.is_active = True
            authority.routing_enabled = True
            authority.notifications_enabled = True
            authority.operating_hours = operating_hours
            authority.physical_address = physical_address
            authority.service_hub = service_hub

        contacts = item.get("contacts") or []
        for contact in contacts:
            contact_type = (contact.get("type") or "primary").strip().lower()
            channel = (contact.get("channel") or "").strip().lower()
            value = (contact.get("value") or "").strip()
            is_primary = contact_type == "primary"
            is_secondary = contact_type == "secondary"
            verification_status = (
                (contact.get("verification_status") or "unverified").strip().lower()
            )
            source_url = (contact.get("source_url") or "").strip() or None
            notes = (contact.get("notes") or "").strip() or None
            after_hours = _to_bool(contact.get("after_hours"))
            if not channel or not value:
                continue
            existing = DepartmentContact.query.filter(
                DepartmentContact.authority_id == authority.id,
                DepartmentContact.contact_type == contact_type,
                DepartmentContact.channel == channel,
                DepartmentContact.value == value,
            ).first()
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
                seeded_contacts += 1
                continue

            existing.is_active = True
            existing.is_primary = is_primary
            existing.is_secondary = is_secondary
            existing.verification_status = verification_status
            existing.source_url = source_url
            existing.notes = notes
            existing.after_hours = after_hours

        known_contact_keys = {
            (
                (contact.get("type") or "primary").strip().lower(),
                (contact.get("channel") or "").strip().lower(),
                (contact.get("value") or "").strip(),
            )
            for contact in contacts
            if (contact.get("channel") or "").strip() and (contact.get("value") or "").strip()
        }
        existing_contacts = DepartmentContact.query.filter(
            DepartmentContact.authority_id == authority.id
        ).all()
        for existing in existing_contacts:
            key = (existing.contact_type, existing.channel, existing.value)
            if key not in known_contact_keys:
                existing.is_active = False

    db.session.commit()
    return seeded_departments, seeded_contacts


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        created_departments, created_contacts = seed_departments()
        print(f"Departments created: {created_departments}")
        print(f"Contacts created: {created_contacts}")
