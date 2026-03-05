import pytest

from app import create_app
from app.extensions import db


@pytest.fixture()
def app():
    app = create_app("testing")

    app.config.update(
        TESTING=True,
        # Disable CSRF so form POSTs work in tests
        WTF_CSRF_ENABLED=False,
        # Prevent Flask-Login session protection from invalidating test sessions
        SESSION_PROTECTION=None,
        # Stable secret key for test sessions
        SECRET_KEY="test-secret-key",
        # Fast in-memory database for tests
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
