from __future__ import annotations

import io
from types import SimpleNamespace

from model import NUM_CLASSES, Prediction
import utils


def test_health_endpoint_reports_ready_local_model(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json()["local_model"] == "ready"


def test_home_page_loads(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Plant AI" in response.data


def test_missing_upload_returns_400(client):
    response = client.post("/predict", data={})

    assert response.status_code == 400
    assert b"choose a plant image" in response.data


def test_non_image_upload_returns_400(client):
    response = client.post(
        "/predict",
        data={"file": (io.BytesIO(b"not an image"), "notes.txt")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert b"valid JPEG, PNG, or WebP" in response.data


def test_valid_upload_renders_local_result(client, jpeg_bytes, monkeypatch):
    monkeypatch.setattr("app.predict_image", lambda _: Prediction("Tomato___healthy", 0.99))

    response = client.post(
        "/predict",
        data={"file": (io.BytesIO(jpeg_bytes), "leaf.jpg")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"Tomato" in response.data
    assert b"Healthy" in response.data
    assert b"99.0%" in response.data


def test_ai_fallback_output_is_escaped(client, jpeg_bytes, monkeypatch):
    monkeypatch.setattr("app.predict_image", lambda _: Prediction("Tomato___healthy", 0.20))
    monkeypatch.setattr("app.is_ai_available", lambda: True)
    monkeypatch.setattr(
        "app.diagnose_with_ai",
        lambda *_: SimpleNamespace(
            plant_name="Unknown",
            likely_condition="Unknown",
            confidence_level="low",
            summary="<script>alert('unsafe')</script>",
            visible_observations=["A green area"],
            possible_causes=["Insufficient visual evidence"],
            recommended_next_steps=["Take a clearer photo"],
            uncertainty_note="Image-only assessment",
        ),
    )

    response = client.post(
        "/predict",
        data={"file": (io.BytesIO(jpeg_bytes), "leaf.jpg")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"<script>" not in response.data
    assert b"&lt;script&gt;" in response.data


def test_user_can_request_ai_for_unsupported_crop(client, jpeg_bytes, monkeypatch):
    monkeypatch.setattr("app.predict_image", lambda _: Prediction("Tomato___healthy", 0.98))
    monkeypatch.setattr("app.is_ai_available", lambda: True)
    monkeypatch.setattr(
        "app.diagnose_with_ai",
        lambda *_: SimpleNamespace(
            plant_name="Cassava",
            likely_condition="Possible mosaic disease",
            confidence_level="medium",
            summary="AI-assisted assessment",
            visible_observations=["Mottled leaf"],
            possible_causes=["Viral disease"],
            recommended_next_steps=["Consult a local extension officer"],
            uncertainty_note="Laboratory confirmation may be needed",
        ),
    )

    response = client.post(
        "/predict",
        data={
            "file": (io.BytesIO(jpeg_bytes), "cassava.jpg"),
            "analysis_mode": "ai",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"Cassava" in response.data
    assert b"AI-assisted analysis was requested" in response.data


def test_every_model_class_has_guidance():
    assert set(NUM_CLASSES) == set(utils.disease_dic)
