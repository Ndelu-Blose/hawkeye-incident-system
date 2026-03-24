# Technical debt register

Intentional backlog items that are **non-blocking** but should not be forgotten. Update this when closing an item or adding a new one.

---

## Flask-Login deprecation warning

**Observed:** During test runs (and potentially dev servers), Python emits:

- `DeprecationWarning: datetime.datetime.utcnow() is deprecated...`

**Origin:** `flask_login`’s `login_manager` (third-party), not HawkEye application code.

**Status:**

- Non-blocking.
- Does not indicate broken authentication or sessions.

**Plan:**

- Revisit during the next **dependency upgrade cycle** (Flask-Login / Flask).
- When upgrading, check Flask-Login release notes for migration away from `utcnow()` in favour of timezone-aware datetimes.
- Only patch locally if we vendor or monkey-patch (not recommended unless unavoidable).

**Priority:** Low.

---

## How to use this file

- Prefer **Checklist.md** for a one-line pointer to active tech debt.
- Use **this file** for slightly more context and history when the checklist would get noisy.
