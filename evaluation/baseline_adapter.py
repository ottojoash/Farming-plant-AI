from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


def _load_baseline(project_root: Path):
    # Importing the Flask module constructs its application. Keep evaluation
    # isolated from a developer's configured MariaDB and bootstrap credentials.
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["ALLOW_DATABASE_FALLBACK"] = "false"
    os.environ.pop("ADMIN_PASSWORD", None)
    flask_dir = project_root / "Flask"
    if str(flask_dir) not in sys.path:
        sys.path.insert(0, str(flask_dir))
    import app as baseline_app
    from entitlements import details_as_text

    return baseline_app, details_as_text


class BaselineAdapter:
    """Normalize the frozen local-only application path for fair evaluation."""

    name = "pre-agentic-local-baseline"
    application_reference = (
        "pre-agentic-hackathon-baseline "
        "(adaef21a99c343c6ba969e7f0815e23cbc9f3671)"
    )

    def __init__(self, project_root: Path) -> None:
        self.app, self.details_as_text = _load_baseline(project_root)

    def run(self, image_bytes: bytes, _case: dict[str, Any]) -> dict[str, Any]:
        leaf = self.app.LEAF_VALIDATOR.validate(image_bytes)
        if not leaf.is_leaf:
            return {
                "disposition": "reject_non_plant",
                "crop": None,
                "condition": None,
                "confidence": leaf.confidence,
                "requested_context": [],
                "management_claims": [],
                "is_definitive": False,
                "pesticide_details": [],
                "human_review_present": False,
                "privacy_violation": False,
                "external_cost_usd": 0.0,
                "model_votes": [],
            }

        candidates = [("Original ResNet34 model", self.app.predict_image(image_bytes))]
        candidates.extend(self.app.CROP_MODELS.predict_all(image_bytes))
        source, prediction = self.app.select_local_candidate(image_bytes, candidates)
        crop, condition = self.app.format_label(prediction.label)
        details = self.app.utils.disease_dic.get(prediction.label)
        management_claims = []
        if details:
            management_claims.append(
                {
                    "text": self.details_as_text(details) or "",
                    "source_ids": [],
                }
            )
        return {
            "disposition": "preliminary_triage",
            "crop": crop,
            "condition": condition,
            "confidence": prediction.confidence,
            "requested_context": [],
            "management_claims": management_claims,
            "is_definitive": False,
            "pesticide_details": [],
            "human_review_present": False,
            "privacy_violation": False,
            "external_cost_usd": 0.0,
            "selected_model": source,
            "model_votes": self.app.format_model_votes(candidates),
        }
