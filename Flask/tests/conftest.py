from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from PIL import Image


FLASK_DIR = Path(__file__).resolve().parents[1]
if str(FLASK_DIR) not in sys.path:
    sys.path.insert(0, str(FLASK_DIR))


@pytest.fixture()
def app():
    from app import create_app

    return create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
        }
    )


@pytest.fixture(autouse=True)
def accept_leaf_images(monkeypatch):
    from leaf_validator import LeafValidation

    monkeypatch.setattr(
        "app.LEAF_VALIDATOR.validate",
        lambda _: LeafValidation(is_leaf=True, confidence=0.99),
    )
    monkeypatch.setattr("app.CROP_MODELS.predict_all", lambda _: [])
    monkeypatch.setattr(
        "app.LEAF_VALIDATOR.crop_probabilities",
        lambda _image, crops: {crop: 1 / len(set(crops)) for crop in set(crops)},
    )


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def jpeg_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (32, 32), color=(45, 130, 70)).save(output, format="JPEG")
    return output.getvalue()
