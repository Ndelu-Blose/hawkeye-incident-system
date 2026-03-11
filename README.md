## Hawkeye – Neighbourhood Safety & Incident Reporting

Hawkeye is a Flask + SQLAlchemy + PostgreSQL web application for reporting and managing neighbourhood safety incidents. It supports **Resident**, **Authority**, and **Admin** roles with secure authentication, audit trails, and email-based notifications.

### Getting started (development)

1. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # macOS/Linux
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment (local)**

   Copy `.env.example` to `.env` and update values (database URL, mail settings, secret key).

   - For local development, `DATABASE_URL` in `.env` is defined in terms of `DB_NAME`, `DB_USER`, and `DB_PASSWORD` and uses `localhost` as the host.
   - When running via Docker Compose, the `web` service constructs its own `DATABASE_URL` from `DB_NAME`, `DB_USER`, and `DB_PASSWORD` with the host set to `db`, so you generally only need to adjust those three variables (plus `SECRET_KEY`).

   **Secret key and cookie security**

   - `SECRET_KEY` **must** be set to a long random value in any non-demo deployment. Flask uses it to sign session cookies and CSRF tokens.
   - In production, Hawkeye enables secure cookie settings (see `app/config.py`):
     - `SESSION_COOKIE_SECURE=True` and `REMEMBER_COOKIE_SECURE=True` (requires HTTPS)
     - `SESSION_COOKIE_HTTPONLY=True` / `REMEMBER_COOKIE_HTTPONLY=True`
     - `SESSION_COOKIE_SAMESITE='Strict'` in production (`'Lax'` in development)
   - If you deploy behind a reverse proxy/HTTPS terminator, ensure the app is served over HTTPS so `Secure` cookies work as intended.

   **Bootstrap admin (for demos)**

   On startup (except in tests), Hawkeye will ensure there is at least one admin user:

   - By default it will create:
     - Email: `admin@example.com`
     - Password: `Admin123!`
   - You can override this via:
     - `ADMIN_EMAIL`
     - `ADMIN_PASSWORD`
     - `ADMIN_NAME`

   For anything beyond local demos, you should **override** these defaults with strong values and treat them like normal credentials.

4. **Run the app (local)**

   ```bash
   python run.py
   ```

### Running with Docker

1. **Create a `.env` file for Docker Compose**

   ```bash
   cp .env.example .env
   # Then edit .env to set at least SECRET_KEY and DB_PASSWORD
   ```

2. **Start the stack (API + Postgres)**

   ```bash
   docker compose up --build
   ```

### Project structure (high level)

- `app/` – Flask application package (config, extensions, models, services, routes, templates, static assets)
- `worker/` – background worker for email notifications (to be implemented)
- `tests/` – unit and integration tests

Further details are documented in the Hawkeye implementation plan.

### Security model (Phase 1)

Hawkeye is designed so that sensitive authentication and admin capabilities behave more like a real SaaS product than a demo app:

- **Password storage**
  - User passwords are never stored in plain text.
  - Passwords are hashed using bcrypt (via `hash_password` / `check_password` in `app/utils/security.py`).
  - Even admins can not view a user’s password – they can only trigger a reset.

- **Admin password resets**
  - The admin user detail screen no longer lets admins type a new password directly.
  - Instead, admins can trigger a password reset, which generates a strong temporary password and hashes it.
  - In non‑production environments the temporary password is surfaced via a flash message to simplify demos; in production only a generic “password reset” message is shown and you would typically wire this to an email flow.

- **Role‑based access control (RBAC)**
  - All admin routes (dashboard, incidents, users, status updates, password resets) are protected with both `@login_required` and `@role_required(Roles.ADMIN)`.
  - Authority‑only endpoints use `@role_required(Roles.AUTHORITY, Roles.ADMIN)` so admins can assist with triage while residents remain restricted to their own incidents.
  - Admins cannot deactivate their own account from the admin UI while signed in, to reduce the risk of accidentally locking themselves out.

- **Audit trail for privileged actions**
  - An `AdminAuditLog` model records key privileged actions performed by admins:
    - user updates (role / active / verification flags),
    - user password resets,
    - incident status changes made from the admin console.
  - Only high‑level metadata is stored (no passwords or other secrets), and the table can be extended in future phases with a UI or additional actions if needed.

These measures are intentionally lightweight but give Hawkeye a credible security story for Phase 1 while leaving room to evolve toward full email‑based password reset flows, richer audit logging, and finer‑grained permissions in later phases.

