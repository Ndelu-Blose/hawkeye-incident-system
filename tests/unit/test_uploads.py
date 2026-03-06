"""Unit tests for upload validation."""

from app.utils.uploads import allowed_image


def test_allowed_image_accepts_valid_extensions():
    assert allowed_image("photo.jpg") is True
    assert allowed_image("photo.JPG") is True
    assert allowed_image("photo.jpeg") is True
    assert allowed_image("photo.png") is True
    assert allowed_image("photo.webp") is True


def test_allowed_image_rejects_invalid():
    assert allowed_image("file.pdf") is False
    assert allowed_image("file.exe") is False
    assert allowed_image("file") is False
    assert allowed_image("") is False
