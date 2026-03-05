from flask import Flask, abort
from flask_login import AnonymousUserMixin, LoginManager, UserMixin

from app.constants import Roles
from app.utils.decorators import role_required


class DummyUser(UserMixin):
    def __init__(self, user_id: int, role: str) -> None:
        self.id = user_id
        self.role = role


def test_role_required_allows_correct_role(monkeypatch):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"
    login_manager = LoginManager(app)

    @login_manager.user_loader
    def load_user(user_id: str):  # pragma: no cover - test hook
        return DummyUser(int(user_id), Roles.RESIDENT.value)

    @app.route("/protected")
    @role_required(Roles.RESIDENT)
    def protected():
        return "ok"

    with app.test_request_context("/protected"):
        # Patch current_user manually
        from flask_login import utils as login_utils

        monkeypatch.setattr(
            login_utils,
            "_get_user",
            lambda: DummyUser(1, Roles.RESIDENT.value),
        )
        resp = protected()
        assert resp == "ok"


def test_role_required_rejects_anonymous(monkeypatch):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"
    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.unauthorized_handler
    def _unauthorized():
        abort(403)

    @app.route("/protected")
    @role_required(Roles.RESIDENT)
    def protected():
        return "ok"

    from flask_login import utils as login_utils

    monkeypatch.setattr(
        login_utils,
        "_get_user",
        lambda: AnonymousUserMixin(),
    )

    with app.test_request_context("/protected"):
        try:
            protected()
        except Exception as exc:
            assert getattr(exc, "code", None) == 403
