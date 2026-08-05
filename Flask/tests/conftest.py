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

    return create_app({"TESTING": True})


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def jpeg_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (32, 32), color=(45, 130, 70)).save(output, format="JPEG")
    return output.getvalue()
