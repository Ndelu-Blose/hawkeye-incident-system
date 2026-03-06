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
- `tests/` – unit, integration, and security tests (to be implemented)
 - `tests/` – unit and integration tests

Further details are documented in the Hawkeye implementation plan.

