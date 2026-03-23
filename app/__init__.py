import os
from typing import Any

from flask import Flask, render_template
from sqlalchemy.exc import OperationalError, ProgrammingError

from .config import DevelopmentConfig, ProductionConfig, TestingConfig
from .constants import APP_NAME, APP_TAGLINE, Roles
from .extensions import bcrypt, csrf, db, limiter, login_manager, mail, migrate


def create_app(config_name: str | None = None) -> Flask:
    """Application factory for Alertweb Solutions."""
    app = Flask(__name__, instance_relative_config=False)

    # Select configuration
    if config_name is None:
        config_name = os.getenv("FLASK_CONFIG", "development").lower()

    config_mapping: dict[str, type] = {
        "development": DevelopmentConfig,
        "testing": TestingConfig,
        "production": ProductionConfig,
    }
    config_class = config_mapping.get(config_name, DevelopmentConfig)
    app.config.from_object(config_class)

    # Normalize upload folder to an absolute path so send_from_directory works
    # reliably in Docker and on Windows.
    upload_folder = app.config.get("UPLOAD_FOLDER", "instance/uploads")
    if upload_folder and not os.path.isabs(str(upload_folder)):
        repo_root = os.path.abspath(os.path.join(app.root_path, os.pardir))
        app.config["UPLOAD_FOLDER"] = os.path.abspath(os.path.join(repo_root, str(upload_folder)))

    _register_extensions(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_template_globals(app)
    _bootstrap_admin(app)

    from .utils.template_helpers import render_status_badge, sla_due

    app.jinja_env.globals["render_status_badge"] = render_status_badge
    app.jinja_env.filters["sla_due"] = sla_due

    return app


def _register_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)

    from .models.user import User

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:  # type: ignore[override]
        try:
            return User.query.get(int(user_id))
        except (TypeError, ValueError):
            return None

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"


def _register_blueprints(app: Flask) -> None:
    from .routes.admin_routes import admin_bp
    from .routes.auth_routes import auth_bp
    from .routes.authority_routes import authority_bp
    from .routes.main_routes import main_bp
    from .routes.public_routes import public_bp
    from .routes.resident_routes import resident_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(resident_bp, url_prefix="/resident")
    app.register_blueprint(authority_bp, url_prefix="/authority")
    app.register_blueprint(admin_bp, url_prefix="/admin")


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(error: Exception) -> tuple[str, int]:
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(error: Exception) -> tuple[str, int]:
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def server_error(error: Exception) -> tuple[str, int]:
        return render_template("errors/500.html"), 500


def _register_template_globals(app: Flask) -> None:
    from flask_wtf.csrf import generate_csrf

    @app.context_processor
    def inject_globals() -> dict[str, Any]:
        return {
            "APP_NAME": APP_NAME,
            "APP_TAGLINE": APP_TAGLINE,
        }

    @app.context_processor
    def inject_csrf() -> dict[str, Any]:
        # Expose generate_csrf as csrf_token() in templates
        return {"csrf_token": generate_csrf}


def _bootstrap_admin(app: Flask) -> None:
    """Ensure there is at least one admin user.

    Uses environment variables for credentials, with dev-friendly defaults:
    - ADMIN_EMAIL (default: admin@example.com)
    - ADMIN_PASSWORD (default: Admin123!)
    - ADMIN_NAME (default: Alertweb Solutions Admin)
    """
    from app.services.auth_service import auth_service  # local import to avoid cycles

    email = os.getenv("ADMIN_EMAIL", "admin@example.com").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "Admin123!")
    name = os.getenv("ADMIN_NAME", "Alertweb Solutions Admin").strip() or "Alertweb Solutions Admin"

    # In testing we let tests control users explicitly.
    if app.config.get("TESTING"):
        return

    if not email or not password:
        return

    try:
        with app.app_context():
            existing = auth_service.user_repo.get_by_email(email)
            if existing is not None:
                return

            user, errors = auth_service.register_user(
                name=name,
                email=email,
                password=password,
                role=Roles.ADMIN.value,
            )
            if errors:
                app.logger.warning("Failed to bootstrap admin user: %s", "; ".join(errors))
            else:
                app.logger.info("Bootstrap admin created successfully.")
    except (OperationalError, ProgrammingError) as exc:
        app.logger.warning(
            "Skipping admin bootstrap because database schema is not ready yet: %s",
            exc,
        )
