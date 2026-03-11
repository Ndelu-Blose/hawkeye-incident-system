from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select

from app.extensions import db
from app.models.user import User


@dataclass(frozen=True)
class UserPage:
    items: list[User]
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


class UserRepository:
    """Data access helper for User entities."""

    def get_by_id(self, user_id: int) -> User | None:
        return db.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return User.query.filter_by(email=email).one_or_none()

    def add(self, user: User) -> User:
        db.session.add(user)
        return user

    def commit(self) -> None:
        db.session.commit()

    def list_users(
        self,
        *,
        role: str | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> UserPage:
        page = max(1, int(page or 1))
        per_page = min(100, max(1, int(per_page or 25)))

        stmt = select(User)
        if role:
            stmt = stmt.where(User.role == role)

        q = (search or "").strip()
        if q:
            like = f"%{q.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(User.name).like(like),
                    func.lower(User.email).like(like),
                )
            )

        count_stmt = stmt.with_only_columns(func.count(User.id)).order_by(None)
        total = int(db.session.execute(count_stmt).scalar() or 0)

        stmt = stmt.order_by(User.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        items = list(db.session.execute(stmt).scalars().all())
        return UserPage(items=items, total=total, page=page, per_page=per_page)

    def get_stats(self) -> dict[str, int]:
        """Aggregate user counts by role and status for admin dashboards."""
        total = db.session.query(func.count(User.id)).scalar() or 0
        residents = (
            db.session.query(func.count(User.id)).filter(User.role == "resident").scalar() or 0
        )
        authorities = (
            db.session.query(func.count(User.id)).filter(User.role == "authority").scalar() or 0
        )
        admins = db.session.query(func.count(User.id)).filter(User.role == "admin").scalar() or 0
        inactive = (
            db.session.query(func.count(User.id)).filter(User.is_active.is_(False)).scalar() or 0
        )
        return {
            "total": total,
            "residents": residents,
            "authorities": authorities,
            "admins": admins,
            "inactive": inactive,
        }
