"""Capture sanitized representative Plant AI workflow trajectories."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Flask"))

from agent_workflow import PlantTriageWorkflow, WorkflowTools  # noqa: E402
from leaf_validator import LeafValidation  # noqa: E402
from model import Prediction  # noqa: E402


def evidence(crop: str, condition: str) -> list[dict[str, object]]:
    return [
        {
            "id": "trajectory-approved-source",
            "title": "Reviewed crop guidance",
            "summary": "Sanitized fixture evidence summary.",
            "actions": ["Use a low-risk cultural practice and confirm locally."],
            "source_name": "Approved extension source",
            "url": "https://extension.example.edu/reviewed-guidance",
            "corpus_version": "trajectory-fixture-v1",
            "retrieved_at": "2026-08-29",
            "location_note": "Fixture source scope; confirm locally.",
            "crop": crop,
            "condition": condition,
        }
    ]


def build_tools(*, leaf: bool = True, confidence: float = 0.94, fail_vision: bool = False, ai=False):
    calls = {"ai": 0}

    def predict(_image):
        if fail_vision:
            raise RuntimeError("fixture checkpoint unavailable")
        return Prediction("Tomato___Late_blight", confidence)

    def diagnose(*_args):
        calls["ai"] += 1
        if calls["ai"] == 1:
            raise TimeoutError("fixture timeout")
        return SimpleNamespace(
            plant_name="Tomato",
            likely_condition="Late blight",
            confidence_level="medium",
            summary="Sanitized AI assessment fixture.",
            visible_observations=["Dark leaf lesions"],
            possible_causes=["Several causes remain possible"],
            recommended_next_steps=["Confirm with a local plant clinic"],
            uncertainty_note="Image-only screening; confirmation is required.",
        )

    return WorkflowTools(
        validate_leaf=lambda _image: LeafValidation(is_leaf=leaf, confidence=0.98 if leaf else 0.03),
        predict_original=predict,
        predict_registered=lambda _image: [],
        select_candidate=lambda _image, candidates: max(candidates, key=lambda item: item[1].confidence),
        build_local_result=lambda prediction, source: {
            "source": source,
            "is_ai": False,
            "crop": "Tomato",
            "disease": "Late blight",
            "confidence_text": f"{prediction.confidence:.1%}",
            "warning": None,
        },
        format_model_votes=lambda candidates: [
            {"source": source, "prediction": prediction.label} for source, prediction in candidates
        ],
        local_comparison_note=lambda _prediction, _force: "Sanitized local comparison.",
        ai_available=lambda: ai,
        diagnose_ai=diagnose,
        retrieve_evidence=lambda crop, condition, _location: evidence(crop, condition),
        local_confidence_threshold=0.75,
    )


def capture(case_id: str, workflow: PlantTriageWorkflow, **kwargs: object) -> dict[str, object]:
    outcome = workflow.run(b"fixture-image-bytes", "image/jpeg", **kwargs)
    result = outcome.result
    return {
        "case_id": case_id,
        "input": {"image": "fixture bytes omitted", "mime_type": "image/jpeg", "context_fields": sorted((kwargs.get("context") or {}).keys())},
        "tool_contract": ["leaf_validator", "all_registered_vision_models", "evidence_retriever", "verification", "optional_ai"],
        "trace": outcome.trace,
        "output": {
            "disposition": outcome.disposition,
            "crop": result.get("crop"),
            "condition": result.get("disease"),
            "review_checkpoint": result.get("review_checkpoint"),
            "requested_context": outcome.missing_context,
            "evidence_source_ids": [item["id"] for item in result.get("evidence", [])],
            "management_claim_source_ids": [item["source_ids"] for item in result.get("management_claims", [])],
            "errors": outcome.errors,
        },
    }


def main() -> None:
    try:
        source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        source_commit = "unknown"
    trajectories = [
        capture(
            "local_evidence_success",
            PlantTriageWorkflow(build_tools()),
            context={"reported_crop": "Tomato", "symptoms": "Dark lesions"},
        ),
        capture("nonplant_rejection", PlantTriageWorkflow(build_tools(leaf=False))),
        capture(
            "clarification_for_missing_symptoms",
            PlantTriageWorkflow(build_tools(confidence=0.20)),
            context={"reported_crop": "Tomato"},
        ),
        capture("required_tool_safe_failure", PlantTriageWorkflow(build_tools(fail_vision=True))),
        capture(
            "bounded_ai_retry",
            PlantTriageWorkflow(build_tools(confidence=0.20, ai=True)),
            context={"reported_crop": "Tomato", "symptoms": "Dark lesions"},
        ),
    ]
    payload = {
        "schema_version": 1,
        "artifact": "plant-ai-representative-trajectories",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": source_commit,
        "privacy": "Fixture bytes and prompts omitted; only bounded context-field names and sanitized node summaries are retained.",
        "trajectories": trajectories,
    }
    output = ROOT / "docs" / "competition" / "trajectories" / "representative-v1.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(trajectories)} trajectories to {output}")


if __name__ == "__main__":
    main()
