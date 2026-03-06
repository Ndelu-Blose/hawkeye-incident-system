import os
from typing import Any

from flask import Flask, render_template

from .config import DevelopmentConfig, ProductionConfig, TestingConfig
from .constants import APP_NAME, APP_TAGLINE
from .extensions import bcrypt, csrf, db, limiter, login_manager, mail, migrate


def create_app(config_name: str | None = None) -> Flask:
    """Application factory for Hawkeye."""
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

    _register_extensions(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_template_globals(app)

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
    from .routes.resident_routes import resident_bp

    app.register_blueprint(main_bp)
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
