## Hawkeye – Neighbourhood Safety & Incident Reporting

Hawkeye is a Flask + SQLAlchemy + MySQL web application for reporting and managing neighbourhood safety incidents. It supports **Resident**, **Authority**, and **Admin** roles with secure authentication, audit trails, and email-based notifications.

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

3. **Configure environment**

   Copy `.env.example` to `.env` and update values (database URL, mail settings, secret key).

4. **Run the app**

   ```bash
   python run.py
   ```

### Project structure (high level)

- `app/` – Flask application package (config, extensions, models, services, routes, templates, static assets)
- `worker/` – background worker for email notifications (to be implemented)
- `tests/` – unit, integration, and security tests (to be implemented)

Further details are documented in the Hawkeye implementation plan.

