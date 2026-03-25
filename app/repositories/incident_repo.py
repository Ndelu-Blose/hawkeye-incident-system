from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import joinedload

from app.constants import IncidentStatus
from app.extensions import db
from app.models.incident import Incident
from app.models.incident_dispatch import IncidentDispatch
from app.models.incident_ownership_history import IncidentOwnershipHistory
from app.models.incident_sla_tracking import IncidentSlaTracking


@dataclass(frozen=True)
class Page:
    items: list[Incident]
    total: int
    page: int
    per_page: int

    @property
    def pages(self) -> int:
        if self.per_page <= 0:
            return 0
        return max(1, (self.total + self.per_page - 1) // self.per_page)

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages


def _start_of_today_utc() -> datetime:
    return datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def _start_of_week_utc() -> datetime:
    now = datetime.now(UTC)
    return (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


class IncidentRepository:
    """Data access helper for Incident entities."""

    def get_by_id(self, incident_id: int) -> Incident | None:
        return db.session.get(Incident, incident_id)

    def add(self, incident: Incident) -> Incident:
        db.session.add(incident)
        return incident

    def list_for_resident(
        self,
        resident_id: int,
        status: IncidentStatus | None = None,
    ) -> Iterable[Incident]:
        stmt = (
            select(Incident)
            .where(Incident.reported_by_id == resident_id)
            .order_by(Incident.created_at.desc())
        )
        if status is not None:
            stmt = stmt.where(Incident.status == status.value)
        return db.session.execute(stmt).scalars().all()

    def search_for_resident(
        self,
        resident_id: int,
        *,
        status: IncidentStatus | None = None,
        category_id: int | None = None,
        q: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        area: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Page:
        """Resident-facing incident explorer with search, filters, and pagination."""
        page = max(1, int(page or 1))
        per_page = min(100, max(1, int(per_page or 20)))

        stmt = select(Incident).where(Incident.reported_by_id == resident_id)

        if status is not None:
            stmt = stmt.where(Incident.status == status.value)

        if category_id is not None:
            stmt = stmt.where(Incident.category_id == category_id)

        q_norm = (q or "").strip()
        if q_norm:
            like = f"%{q_norm.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Incident.title).like(like),
                    func.lower(Incident.description).like(like),
                    func.lower(Incident.reference_code).like(like),
                    func.lower(Incident.location).like(like),
                    func.lower(Incident.suburb_or_ward).like(like),
                )
            )

        if date_from is not None:
            stmt = stmt.where(
                (Incident.reported_at >= date_from) | (Incident.created_at >= date_from)
            )
        if date_to is not None:
            stmt = stmt.where((Incident.reported_at <= date_to) | (Incident.created_at <= date_to))

        area_norm = (area or "").strip()
        if area_norm:
            area_like = f"%{area_norm.lower()}%"
            # Prefer structured suburb/ward when available, but fall back to legacy field.
            stmt = stmt.where(
                or_(
                    func.lower(Incident.suburb).like(area_like),
                    func.lower(Incident.ward).like(area_like),
                    func.lower(Incident.suburb_or_ward).like(area_like),
                )
            )

        count_stmt = stmt.with_only_columns(func.count(Incident.id)).order_by(None)
        total = int(db.session.execute(count_stmt).scalar() or 0)

        stmt = (
            stmt.order_by(Incident.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        )
        items = list(db.session.execute(stmt).scalars().unique().all())
        return Page(items=items, total=total, page=page, per_page=per_page)

    def find_recent_similar(
        self,
        category: str,
        suburb_or_ward: str,
        hours: int = 24,
        limit: int = 5,
    ) -> list[Incident]:
        since = datetime.now(UTC) - timedelta(hours=hours)
        stmt = (
            select(Incident)
            .where(Incident.category == category)
            .where(Incident.suburb_or_ward == suburb_or_ward)
            .where(Incident.created_at >= since)
            .order_by(Incident.created_at.desc())
            .limit(limit)
        )
        return list(db.session.execute(stmt).scalars().all())

    # In future this repository can grow methods that leverage the new
    # latitude/longitude fields for radius-based similarity or GIS queries.

    def list_for_authority(
        self,
        status: IncidentStatus | None = None,
        authority_id: int | None = None,
        load_relations: bool = False,
        queue: str | None = None,
    ) -> Iterable[Incident]:
        """queue: incoming|acknowledged|in_progress|completed for dispatch+ownership-based filtering."""
        stmt = select(Incident).order_by(Incident.created_at.desc())
        if status is not None:
            stmt = stmt.where(Incident.status == status.value)
        if authority_id is not None:
            if queue == "incoming":
                has_pending = exists().where(
                    and_(
                        IncidentDispatch.incident_id == Incident.id,
                        IncidentDispatch.authority_id == authority_id,
                        IncidentDispatch.status != "acknowledged",
                    )
                )
                stmt = stmt.where(
                    Incident.status == IncidentStatus.ASSIGNED.value,
                    or_(
                        Incident.current_authority_id == authority_id,
                        exists().where(
                            and_(
                                IncidentOwnershipHistory.incident_id == Incident.id,
                                IncidentOwnershipHistory.authority_id == authority_id,
                                IncidentOwnershipHistory.is_current.is_(True),
                            )
                        ),
                    ),
                    has_pending,
                )
            elif queue == "acknowledged":
                subq = exists().where(
                    and_(
                        IncidentOwnershipHistory.incident_id == Incident.id,
                        IncidentOwnershipHistory.authority_id == authority_id,
                        IncidentOwnershipHistory.is_current.is_(True),
                    )
                )
                stmt = stmt.where(
                    Incident.status == IncidentStatus.ACKNOWLEDGED.value,
                    subq,
                )
            elif queue == "in_progress":
                subq = exists().where(
                    and_(
                        IncidentOwnershipHistory.incident_id == Incident.id,
                        IncidentOwnershipHistory.authority_id == authority_id,
                        IncidentOwnershipHistory.is_current.is_(True),
                    )
                )
                stmt = stmt.where(
                    Incident.status == IncidentStatus.IN_PROGRESS.value,
                    subq,
                )
            elif queue == "completed":
                # Use ownership_history: incidents resolved/closed where this authority
                # was the last owner (has an ownership row for this incident).
                subq = exists().where(
                    and_(
                        IncidentOwnershipHistory.incident_id == Incident.id,
                        IncidentOwnershipHistory.authority_id == authority_id,
                    )
                )
                stmt = stmt.where(
                    Incident.status.in_(
                        (IncidentStatus.RESOLVED.value, IncidentStatus.CLOSED.value)
                    ),
                    subq,
                )
            else:
                stmt = stmt.where(Incident.current_authority_id == authority_id)
        if load_relations:
            stmt = stmt.options(
                joinedload(Incident.category_rel),
                joinedload(Incident.location_rel),
                joinedload(Incident.current_authority),
            )
        return db.session.execute(stmt).scalars().unique().all()

    def list_for_admin(
        self,
        *,
        status: IncidentStatus | None = None,
        category: str | None = None,
        severity: str | None = None,
        authority_id: int | None = None,
        unassigned_only: bool = False,
        q: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        area: str | None = None,
        sort: str | None = None,
        page: int = 1,
        per_page: int = 25,
        load_relations: bool = True,
    ) -> Page:
        """Admin incident list with filters (including date/area) + pagination."""
        page = max(1, int(page or 1))
        per_page = min(100, max(1, int(per_page or 25)))

        stmt = select(Incident)

        if status is not None:
            stmt = stmt.where(Incident.status == status.value)
        if category:
            stmt = stmt.where(Incident.category == category)
        if severity:
            stmt = stmt.where(Incident.severity == severity)
        if authority_id is not None:
            stmt = stmt.where(Incident.current_authority_id == authority_id)
        if unassigned_only:
            stmt = stmt.where(Incident.current_authority_id.is_(None))

        q_norm = (q or "").strip()
        if q_norm:
            like = f"%{q_norm.lower()}%"
            filters = [
                func.lower(Incident.title).like(like),
                func.lower(Incident.reference_code).like(like),
            ]
            if q_norm.isdigit():
                try:
                    filters.append(Incident.id == int(q_norm))
                except ValueError:
                    pass
            stmt = stmt.where(or_(*filters))

        if date_from is not None:
            stmt = stmt.where(
                (Incident.reported_at >= date_from) | (Incident.created_at >= date_from)
            )
        if date_to is not None:
            stmt = stmt.where((Incident.reported_at <= date_to) | (Incident.created_at <= date_to))

        area_norm = (area or "").strip()
        if area_norm:
            area_like = f"%{area_norm.lower()}%"
            stmt = stmt.where(func.lower(Incident.suburb_or_ward).like(area_like))

        if load_relations:
            stmt = stmt.options(
                joinedload(Incident.category_rel),
                joinedload(Incident.location_rel),
                joinedload(Incident.current_authority),
                joinedload(Incident.reporter),
            )

        count_stmt = stmt.with_only_columns(func.count(Incident.id)).order_by(None)
        total = int(db.session.execute(count_stmt).scalar() or 0)

        sort_key = (sort or "newest").lower()
        if sort_key == "oldest":
            order_clause = Incident.created_at.asc()
        else:
            order_clause = Incident.created_at.desc()

        stmt = stmt.order_by(order_clause).offset((page - 1) * per_page).limit(per_page)
        items = list(db.session.execute(stmt).scalars().unique().all())
        return Page(items=items, total=total, page=page, per_page=per_page)

    def count_new_today(self) -> int:
        since = _start_of_today_utc()
        stmt = select(func.count(Incident.id)).where(
            (Incident.reported_at >= since) | (Incident.created_at >= since)
        )
        return db.session.execute(stmt).scalar() or 0

    def count_unassigned(self) -> int:
        closed_statuses = (
            IncidentStatus.RESOLVED.value,
            IncidentStatus.REJECTED.value,
            IncidentStatus.CLOSED.value,
        )
        stmt = select(func.count(Incident.id)).where(
            Incident.current_authority_id.is_(None),
            Incident.status.notin_(closed_statuses),
        )
        return db.session.execute(stmt).scalar() or 0

    def count_in_progress(self) -> int:
        stmt = select(func.count(Incident.id)).where(
            Incident.status.in_((IncidentStatus.IN_PROGRESS.value, IncidentStatus.ASSIGNED.value))
        )
        return db.session.execute(stmt).scalar() or 0

    def count_resolved_this_week(self) -> int:
        since = _start_of_week_utc()
        stmt = select(func.count(Incident.id)).where(
            Incident.status.in_((IncidentStatus.RESOLVED.value, IncidentStatus.CLOSED.value)),
            Incident.resolved_at >= since,
        )
        return db.session.execute(stmt).scalar() or 0

    def count_overdue(self) -> int:
        """Incidents not resolved/rejected/closed and past SLA (reported_at + category default_sla_hours)."""
        now = datetime.now(UTC)
        sla_stmt = select(func.count(IncidentSlaTracking.id)).where(
            IncidentSlaTracking.status == "breached",
            IncidentSlaTracking.deadline_at <= now,
        )
        sla_count = int(db.session.execute(sla_stmt).scalar() or 0)
        if sla_count > 0:
            return sla_count

        from app.models import IncidentCategory

        closed_statuses = (
            IncidentStatus.RESOLVED.value,
            IncidentStatus.REJECTED.value,
            IncidentStatus.CLOSED.value,
        )
        stmt = (
            select(Incident)
            .outerjoin(IncidentCategory, Incident.category_id == IncidentCategory.id)
            .where(Incident.status.notin_(closed_statuses))
            .where(Incident.reported_at.isnot(None))
            .options(joinedload(Incident.category_rel))
        )
        incidents = list(db.session.execute(stmt).scalars().unique().all())
        count = 0
        for inc in incidents:
            reported_at = inc.reported_at
            if reported_at is None:
                continue
            if reported_at.tzinfo is None:
                reported_at = reported_at.replace(tzinfo=UTC)
            sla_hours = 72
            if inc.category_rel is not None and inc.category_rel.default_sla_hours is not None:
                sla_hours = inc.category_rel.default_sla_hours
            elif inc.category_id:
                cat = db.session.get(IncidentCategory, inc.category_id)
                if cat and cat.default_sla_hours is not None:
                    sla_hours = cat.default_sla_hours
            due = reported_at + timedelta(hours=sla_hours)
            if due < now:
                count += 1
        return count

    def list_recent(self, *, limit: int = 5, load_relations: bool = True) -> list[Incident]:
        """Return the most recently created incidents for dashboard views."""
        stmt = select(Incident)
        if load_relations:
            stmt = stmt.options(
                joinedload(Incident.category_rel),
                joinedload(Incident.location_rel),
                joinedload(Incident.current_authority),
                joinedload(Incident.reporter),
            )
        stmt = stmt.order_by(Incident.created_at.desc()).limit(limit)
        return list(db.session.execute(stmt).scalars().unique().all())

    def list_distinct_areas(self) -> list[str]:
        """Return distinct area names (suburb/ward) for public area selector."""
        stmt = (
            select(Incident.suburb_or_ward)
            .where(Incident.suburb_or_ward.isnot(None))
            .where(Incident.suburb_or_ward != "")
            .distinct()
            .order_by(Incident.suburb_or_ward)
        )
        rows = db.session.execute(stmt).scalars().all()
        return [r[0] for r in rows if r[0]]

    def search_public(
        self,
        *,
        area: str,
        category_id: int | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Page:
        """Public anonymised incident list by area. No reporter or PII exposed."""
        page = max(1, int(page or 1))
        per_page = min(50, max(1, int(per_page or 20)))

        area_norm = (area or "").strip()
        if not area_norm:
            return Page(items=[], total=0, page=1, per_page=per_page)

        area_like = f"%{area_norm.lower()}%"
        stmt = select(Incident).where(
            or_(
                func.lower(Incident.suburb).like(area_like),
                func.lower(Incident.ward).like(area_like),
                func.lower(Incident.suburb_or_ward).like(area_like),
            )
        )
        # Exclude rejected from public view
        stmt = stmt.where(Incident.status != IncidentStatus.REJECTED.value)

        if category_id is not None:
            stmt = stmt.where(Incident.category_id == category_id)
        if status:
            stmt = stmt.where(Incident.status == status)

        if date_from is not None:
            stmt = stmt.where(
                (Incident.reported_at >= date_from) | (Incident.created_at >= date_from)
            )
        if date_to is not None:
            stmt = stmt.where((Incident.reported_at <= date_to) | (Incident.created_at <= date_to))

        count_stmt = stmt.with_only_columns(func.count(Incident.id)).order_by(None)
        total = int(db.session.execute(count_stmt).scalar() or 0)

        stmt = stmt.options(joinedload(Incident.category_rel))
        stmt = (
            stmt.order_by(Incident.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        )
        items = list(db.session.execute(stmt).unique().scalars().all())
        return Page(items=items, total=total, page=page, per_page=per_page)

    def list_overdue(self, *, limit: int = 5) -> list[Incident]:
        """Return a small list of overdue incidents for dashboards."""
        now = datetime.now(UTC)
        sla_stmt = (
            select(Incident)
            .join(IncidentSlaTracking, IncidentSlaTracking.incident_id == Incident.id)
            .where(
                IncidentSlaTracking.status == "breached",
                IncidentSlaTracking.deadline_at <= now,
            )
            .options(
                joinedload(Incident.category_rel),
                joinedload(Incident.location_rel),
                joinedload(Incident.current_authority),
                joinedload(Incident.reporter),
            )
            .order_by(IncidentSlaTracking.deadline_at.asc())
            .limit(limit)
        )
        sla_items = list(db.session.execute(sla_stmt).scalars().unique().all())
        if sla_items:
            return sla_items

        from app.models import IncidentCategory

        closed_statuses = (
            IncidentStatus.RESOLVED.value,
            IncidentStatus.REJECTED.value,
            IncidentStatus.CLOSED.value,
        )
        stmt = (
            select(Incident)
            .outerjoin(IncidentCategory, Incident.category_id == IncidentCategory.id)
            .where(Incident.status.notin_(closed_statuses))
            .where(Incident.reported_at.isnot(None))
            .options(
                joinedload(Incident.category_rel),
                joinedload(Incident.location_rel),
                joinedload(Incident.current_authority),
                joinedload(Incident.reporter),
            )
        )
        overdue: list[Incident] = []
        for inc in db.session.execute(stmt).scalars().unique().all():
            reported_at = inc.reported_at
            if reported_at is None:
                continue
            if reported_at.tzinfo is None:
                reported_at = reported_at.replace(tzinfo=UTC)
            sla_hours = 72
            if inc.category_rel is not None and inc.category_rel.default_sla_hours is not None:
                sla_hours = inc.category_rel.default_sla_hours
            elif inc.category_id:
                cat = db.session.get(IncidentCategory, inc.category_id)
                if cat and cat.default_sla_hours is not None:
                    sla_hours = cat.default_sla_hours
            due = reported_at + timedelta(hours=sla_hours)
            if due < now:
                overdue.append(inc)
                if len(overdue) >= limit:
                    break
        return overdue
