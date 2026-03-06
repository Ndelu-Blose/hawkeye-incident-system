import shutil
import tempfile

import pytest

from app import create_app
from app.extensions import db


# Minimal 1x1 PNG (valid image for upload tests)
MINIMAL_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture()
def app():
    app = create_app("testing")
    tmp_upload = tempfile.mkdtemp()

    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SESSION_PROTECTION=None,
        SECRET_KEY="test-secret-key",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=tmp_upload,
        MAX_MEDIA_PER_INCIDENT=5,
        MAX_IMAGE_SIZE=5 * 1024 * 1024,
    )

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
    try:
        shutil.rmtree(tmp_upload)
    except OSError:
        pass

@pytest.fixture()
def client(app):
    return app.test_client()
