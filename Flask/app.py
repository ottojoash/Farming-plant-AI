from __future__ import annotations

import base64
import io
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from PIL import Image, UnidentifiedImageError
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from accounts import accounts, payment_webhooks, pricing
from ai_diagnosis import diagnose_with_ai, is_ai_available
from crop_models import CropModelRegistry
from database import User, bootstrap_admin, db, get_int_setting, seed_defaults
from entitlements import record_successful_scan, scan_allowance
from leaf_validator import LeafValidator
from model import Prediction, predict_image
import utils


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")

ALLOWED_IMAGE_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
LOCAL_CONFIDENCE_THRESHOLD = float(os.getenv("LOCAL_CONFIDENCE_THRESHOLD", "0.75"))

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)
CROP_MODELS = CropModelRegistry(BASE_DIR.parent)
LEAF_VALIDATOR = LeafValidator()
LOGIN_MANAGER = LoginManager()
CSRF = CSRFProtect()


def resolve_database_uri(test_config: dict | None) -> tuple[str, str]:
    if test_config and test_config.get("SQLALCHEMY_DATABASE_URI"):
        return test_config["SQLALCHEMY_DATABASE_URI"], "test"
    primary = os.getenv("DATABASE_URL", "sqlite:///plant_ai.db")
    if not os.getenv("ALLOW_DATABASE_FALLBACK", "false").lower() == "true":
        return primary, "mysql" if primary.startswith(("mysql", "mariadb")) else "sqlite"
    try:
        engine = create_engine(primary, pool_pre_ping=True)
        with engine.connect():
            pass
        engine.dispose()
        return primary, "mysql" if primary.startswith(("mysql", "mariadb")) else "sqlite"
    except SQLAlchemyError:
        logger.warning("Primary database unavailable; using configured local fallback")
        return os.getenv("DATABASE_FALLBACK_URL", "sqlite:///plant_ai.db"), "sqlite_fallback"


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    database_uri, database_backend = resolve_database_uri(test_config)
    app.config.update(
        MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES,
        SECRET_KEY=os.getenv("FLASK_SECRET_KEY", "development-only-change-me"),
        SQLALCHEMY_DATABASE_URI=database_uri,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        DATABASE_BACKEND=database_backend,
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    LOGIN_MANAGER.init_app(app)
    LOGIN_MANAGER.login_view = "accounts.login"
    LOGIN_MANAGER.login_message = "Please log in to continue."
    CSRF.init_app(app)
    app.register_blueprint(accounts)
    app.register_blueprint(payment_webhooks)
    CSRF.exempt(payment_webhooks)

    @LOGIN_MANAGER.user_loader
    def load_user(user_id: str):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    with app.app_context():
        db.create_all()
        seed_defaults()
        if not app.config.get("TESTING"):
            bootstrap_admin()

    def home_context(**extra):
        context = {
            "ai_available": is_ai_available(),
            "model_count": 1 + len(CROP_MODELS.available_crops()),
            "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
            "allowance": scan_allowance(),
            "pricing": pricing(),
            "free_account_limit": get_int_setting("free_monthly_scan_limit"),
        }
        context.update(extra)
        return context

    @app.get("/")
    def home():
        return render_template("index.html", **home_context())

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "local_model": "ready",
            "leaf_validator": "ready",
            "ai_fallback": "ready" if is_ai_available() else "not_configured",
            "database": app.config["DATABASE_BACKEND"],
        }

    @app.post("/predict")
    def predict():
        allowance = scan_allowance()
        if not allowance["allowed"]:
            return (
                render_template(
                    "index.html",
                    **home_context(limit_reached=True, allowance=allowance),
                ),
                403,
            )
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
            leaf_validation = LEAF_VALIDATOR.validate(image_bytes)
            if not leaf_validation.is_leaf:
                logger.info("Rejected non-leaf upload with leaf confidence %.3f", leaf_validation.confidence)
                return _render_upload_error(
                    "This image does not appear to contain a clear plant leaf. Please upload a close, "
                    "well-lit photograph of a living leaf.",
                    422,
                )
            local_candidates = [("Original ResNet34 model", predict_image(image_bytes))]
            local_candidates.extend(CROP_MODELS.predict_all(image_bytes))
            local_source, local_prediction = select_local_candidate(image_bytes, local_candidates)
            result = build_local_result(local_prediction, local_source)
            result["local_note"] = (
                f"Plant AI automatically compared {len(local_candidates)} disease models and selected "
                f"the strongest crop-aware match from {local_source}."
            )
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

            result["model_votes"] = format_model_votes(local_candidates)

            try:
                history_confidence = None if result["is_ai"] else local_prediction.confidence
                record_successful_scan(result, history_confidence)
            except SQLAlchemyError:
                db.session.rollback()
                logger.exception("Could not record scan usage")

            return render_template(
                "display_signed_in.html" if current_user.is_authenticated else "display.html",
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
        if current_user.is_authenticated:
            return (
                render_template(
                    "dashboard_scan.html",
                    allowance=scan_allowance(),
                    max_upload_mb=MAX_UPLOAD_BYTES // (1024 * 1024),
                    error=message,
                ),
                status_code,
            )
        return (
            render_template(
                "index.html",
                **home_context(error=message),
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


def build_local_result(prediction: Prediction, source: str = "Local ResNet34 model") -> dict:
    crop, disease = format_label(prediction.label)
    return {
        "source": source,
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


def format_model_votes(candidates: list[tuple[str, Prediction]]) -> list[dict[str, str]]:
    votes = []
    for source, prediction in sorted(candidates, key=lambda item: item[1].confidence, reverse=True):
        crop, disease = format_label(prediction.label)
        votes.append(
            {
                "source": source,
                "prediction": f"{crop} - {disease}",
                "confidence": f"{prediction.confidence:.1%}",
            }
        )
    return votes


def select_local_candidate(
    image_bytes: bytes,
    candidates: list[tuple[str, Prediction]],
) -> tuple[str, Prediction]:
    """Select across closed-set models using disease confidence and visual crop relevance."""
    candidate_crops = [format_label(prediction.label)[0] for _, prediction in candidates]
    try:
        crop_probabilities = LEAF_VALIDATOR.crop_probabilities(image_bytes, candidate_crops)
    except Exception:
        logger.exception("Crop-aware model routing failed; falling back to confidence")
        crop_probabilities = {crop: 1.0 for crop in candidate_crops}

    def routing_score(candidate: tuple[str, Prediction]) -> float:
        crop, _ = format_label(candidate[1].label)
        crop_match = crop_probabilities.get(crop, 0.0)
        return candidate[1].confidence * (0.25 + 0.75 * crop_match)

    return max(candidates, key=routing_score)


def trusted_references() -> list[dict]:
    return [
        {
            "title": "Improve the evidence before deciding",
            "summary": (
                "A diagnosis is only as reliable as the photo and context provided. Photograph a "
                "living symptomatic plant in natural light and compare it with a healthy plant nearby."
            ),
            "tips": [
                "Capture both the top and underside of the affected leaf.",
                "Fill the frame and keep symptoms sharply focused.",
                "Include unusual stems, stalks, roots, or lesions when relevant.",
                "Seek laboratory confirmation when an image cannot distinguish the cause.",
            ],
            "source_name": "University of Minnesota Extension",
            "url": "https://extension.umn.edu/crop-production/digital-crop-doc",
        },
        {
            "title": "Treat only after confirming the cause",
            "summary": (
                "Plant damage may come from pests, watering, drainage, chemicals, weather, or physical "
                "injury. Confirm the cause and try suitable nonchemical controls before using a pesticide."
            ),
            "tips": [
                "If treatment is justified, choose the least-toxic effective option.",
                "The label must list the crop, site, and target problem.",
                "Follow label amounts, timing, protective equipment, storage, and disposal instructions.",
                "Avoid applications during wind or expected rain and prevent runoff.",
            ],
            "source_name": "UC Integrated Pest Management",
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
