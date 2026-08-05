from __future__ import annotations

import base64
import io
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request
from PIL import Image, UnidentifiedImageError

from ai_diagnosis import diagnose_with_ai, is_ai_available
from model import Prediction, predict_image
import utils


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")

ALLOWED_IMAGE_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
LOCAL_CONFIDENCE_THRESHOLD = float(os.getenv("LOCAL_CONFIDENCE_THRESHOLD", "0.75"))

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES,
        SECRET_KEY=os.getenv("FLASK_SECRET_KEY", "development-only-change-me"),
    )
    if test_config:
        app.config.update(test_config)

    @app.get("/")
    def home():
        return render_template(
            "index.html",
            ai_available=is_ai_available(),
            max_upload_mb=MAX_UPLOAD_BYTES // (1024 * 1024),
        )

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "local_model": "ready",
            "ai_fallback": "ready" if is_ai_available() else "not_configured",
        }

    @app.post("/predict")
    def predict():
        uploaded_file = request.files.get("file")
        if uploaded_file is None or not uploaded_file.filename:
            return _render_upload_error("Please choose a plant image to analyse.", 400)

        image_bytes = uploaded_file.read()
        try:
            mime_type = validate_image(image_bytes)
            preview_url = create_preview_data_url(image_bytes)
        except ValueError as exc:
            return _render_upload_error(str(exc), 400)

        try:
            local_prediction = predict_image(image_bytes)
            result = build_local_result(local_prediction)
            force_ai = request.form.get("analysis_mode") == "ai"

            if force_ai or local_prediction.confidence < LOCAL_CONFIDENCE_THRESHOLD:
                if is_ai_available():
                    try:
                        ai_result = diagnose_with_ai(image_bytes, mime_type)
                        result = {
                            "source": "AI-assisted fallback",
                            "is_ai": True,
                            "crop": ai_result.plant_name,
                            "disease": ai_result.likely_condition,
                            "confidence_text": ai_result.confidence_level.title(),
                            "summary": ai_result.summary,
                            "observations": ai_result.visible_observations,
                            "causes": ai_result.possible_causes,
                            "actions": ai_result.recommended_next_steps,
                            "warning": ai_result.uncertainty_note,
                            "local_note": local_comparison_note(local_prediction, force_ai),
                        }
                    except Exception:
                        logger.exception("AI-assisted fallback failed")
                        if force_ai and local_prediction.confidence >= LOCAL_CONFIDENCE_THRESHOLD:
                            result["warning"] = (
                                "The requested AI-assisted analysis is temporarily unavailable. "
                                "The closest local-model result is shown instead."
                            )
                        else:
                            result["warning"] = (
                                "The AI-assisted fallback is temporarily unavailable and the local result is "
                                "below the acceptance threshold. Please try again or consult a plant specialist."
                            )
                else:
                    if force_ai and local_prediction.confidence >= LOCAL_CONFIDENCE_THRESHOLD:
                        result["warning"] = (
                            "AI-assisted analysis was requested but OPENAI_API_KEY is not configured. "
                            "The closest local-model result is shown instead."
                        )
                    else:
                        result["warning"] = (
                            "This local prediction is below the acceptance threshold. Configure "
                            "OPENAI_API_KEY to enable the AI-assisted fallback, or consult a plant specialist."
                        )

            return render_template(
                "display.html",
                result=result,
                preview_url=preview_url,
                references=trusted_references(),
            )
        except Exception:
            logger.exception("Plant diagnosis failed")
            return _render_upload_error(
                "We could not analyse this image. Please try a clear photo of a living leaf.", 500
            )

    @app.errorhandler(413)
    def upload_too_large(_error):
        return _render_upload_error(
            f"The image is too large. Upload an image smaller than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
            413,
        )

    def _render_upload_error(message: str, status_code: int):
        return (
            render_template(
                "index.html",
                error=message,
                ai_available=is_ai_available(),
                max_upload_mb=MAX_UPLOAD_BYTES // (1024 * 1024),
            ),
            status_code,
        )

    return app


def validate_image(image_bytes: bytes) -> str:
    if not image_bytes:
        raise ValueError("The uploaded file is empty.")

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            if image.width * image.height > 25_000_000:
                raise ValueError("The image dimensions are too large. Please upload a smaller photo.")
            image.verify()
            image_format = image.format
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Upload a valid JPEG, PNG, or WebP image.") from exc

    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise ValueError("Unsupported image type. Please use JPEG, PNG, or WebP.")
    return ALLOWED_IMAGE_FORMATS[image_format]


def create_preview_data_url(image_bytes: bytes) -> str:
    with Image.open(io.BytesIO(image_bytes)) as image:
        preview = image.convert("RGB")
        preview.thumbnail((900, 900))
        output = io.BytesIO()
        preview.save(output, format="JPEG", quality=82, optimize=True)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def format_label(label: str) -> tuple[str, str]:
    crop, disease = label.split("___", maxsplit=1)
    crop = crop.replace("_(including_sour)", "").replace("_(maize)", "")
    crop = crop.replace("_", " ").replace(",", "").strip()
    disease = disease.replace("_", " ").strip()
    if disease.lower() == "healthy":
        disease = "Healthy"
    return crop, disease


def build_local_result(prediction: Prediction) -> dict:
    crop, disease = format_label(prediction.label)
    return {
        "source": "Local ResNet34 model",
        "is_ai": False,
        "crop": crop,
        "disease": disease,
        "confidence_text": f"{prediction.confidence:.1%}",
        "details_html": utils.disease_dic.get(prediction.label),
        "warning": None,
    }


def local_comparison_note(prediction: Prediction, force_ai: bool) -> str:
    crop, disease = format_label(prediction.label)
    closest_match = f"{crop} - {disease} at {prediction.confidence:.1%}"
    if force_ai and prediction.confidence >= LOCAL_CONFIDENCE_THRESHOLD:
        return f"AI-assisted analysis was requested. The local model's closest match was {closest_match}."
    return (
        f"The local model's closest match was {closest_match}, below the "
        f"{LOCAL_CONFIDENCE_THRESHOLD:.0%} acceptance threshold."
    )


def trusted_references() -> list[dict[str, str]]:
    return [
        {
            "name": "University of Minnesota Extension — diagnostic photo guidance",
            "url": "https://extension.umn.edu/crop-production/digital-crop-doc",
        },
        {
            "name": "UC Integrated Pest Management — pesticide safety",
            "url": "https://ipm.ucanr.edu/home-and-landscape/understanding-pesticides/",
        },
    ]


app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
