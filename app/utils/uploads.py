"""Helpers for incident evidence image uploads."""

from __future__ import annotations

import secrets
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models.incident import Incident
from app.models.incident_media import IncidentMedia

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def allowed_image(filename: str) -> bool:
    """Return True if filename has an allowed image extension."""
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[-1].lower()
    return ext in ALLOWED_EXTENSIONS


def _safe_filename(original: str) -> str:
    """Generate a safe storage filename."""
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else "jpg"
    if ext not in ALLOWED_EXTENSIONS:
        ext = "jpg"
    return f"{uuid.uuid4().hex}_{secrets.token_hex(4)}.{ext}"


def save_incident_media(
    incident: Incident,
    files: list[FileStorage],
) -> tuple[list[IncidentMedia], list[str]]:
    """
    Validate, store, and create IncidentMedia rows for uploaded files.
    Incident must have an id (session flushed or committed).
    Returns (created_media_list, list of error messages).
    """
    errors: list[str] = []
    created: list[IncidentMedia] = []
    if not incident.id:
        errors.append("Incident must be persisted before adding media.")
        return created, errors

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    incident_dir = upload_folder / "incidents" / str(incident.id)
    max_per_incident = current_app.config.get("MAX_MEDIA_PER_INCIDENT", 5)
    max_size = current_app.config.get("MAX_IMAGE_SIZE", 5 * 1024 * 1024)

    existing_count = incident.media.count()
    if existing_count >= max_per_incident:
        errors.append(f"Maximum {max_per_incident} images per incident allowed.")
        return created, errors

    incident_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        if not f or not f.filename:
            continue
        if existing_count + len(created) >= max_per_incident:
            errors.append(f"Maximum {max_per_incident} images per incident allowed.")
            break
        if not allowed_image(f.filename):
            errors.append(f"File type not allowed: {f.filename}")
            continue
        f.seek(0, 2)
        size = f.tell()
        f.seek(0)
        if size > max_size:
            errors.append(f"File too large: {f.filename} (max 5MB each).")
            continue
        safe_name = _safe_filename(f.filename)
        dest = incident_dir / safe_name
        try:
            f.save(str(dest))
        except OSError as e:
            errors.append(f"Could not save file: {e}")
            continue
        relative_path = f"incidents/{incident.id}/{safe_name}"
        media = IncidentMedia(
            incident_id=incident.id,
            file_path=relative_path,
            original_filename=f.filename,
            content_type=f.content_type,
            filesize_bytes=size,
        )
        db.session.add(media)
        created.append(media)
    return created, errors
