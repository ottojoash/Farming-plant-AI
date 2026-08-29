from __future__ import annotations

import json
from types import SimpleNamespace

from agent_workflow import PlantTriageWorkflow, WorkflowTools
from leaf_validator import LeafValidation
from model import Prediction


def make_tools(**overrides):
    defaults = {
        "validate_leaf": lambda _image: LeafValidation(is_leaf=True, confidence=0.98),
        "predict_original": lambda _image: Prediction("Tomato___healthy", 0.91),
        "predict_registered": lambda _image: [
            ("Beans model", Prediction("Common_bean___Bean_rust", 0.70))
        ],
        "select_candidate": lambda _image, candidates: max(
            candidates, key=lambda candidate: candidate[1].confidence
        ),
        "build_local_result": lambda prediction, source: {
            "source": source,
            "is_ai": False,
            "crop": prediction.label.split("___")[0].replace("_", " "),
            "disease": prediction.label.split("___")[1].replace("_", " ").title(),
            "confidence_text": f"{prediction.confidence:.1%}",
            "warning": None,
        },
        "format_model_votes": lambda candidates: [
            {"source": source, "prediction": prediction.label}
            for source, prediction in candidates
        ],
        "local_comparison_note": lambda _prediction, _force: "Local comparison",
        "ai_available": lambda: False,
        "diagnose_ai": lambda *_: None,
        "retrieve_evidence": lambda _crop, _condition, _location: [],
        "local_confidence_threshold": 0.75,
    }
    defaults.update(overrides)
    return WorkflowTools(**defaults)


def test_non_plant_branch_stops_before_disease_models():
    calls = {"vision": 0}

    def predict(_image):
        calls["vision"] += 1
        return Prediction("Apple___healthy", 0.99)

    workflow = PlantTriageWorkflow(
        make_tools(
            validate_leaf=lambda _image: LeafValidation(is_leaf=False, confidence=0.04),
            predict_original=predict,
        )
    )
    outcome = workflow.run(
        b"image", "image/jpeg", context={"reported_crop": "Cassava", "symptoms": "Mottling"}
    )

    assert outcome.disposition == "reject_non_plant"
    assert calls["vision"] == 0
    assert [event["node"] for event in outcome.trace] == [
        "intake",
        "leaf_gate",
        "finalize_rejection",
    ]


def test_local_branch_runs_all_model_tools_and_returns_serializable_trace():
    workflow = PlantTriageWorkflow(make_tools())
    outcome = workflow.run(
        b"image", "image/jpeg", context={"reported_crop": "Tomato", "symptoms": "Yellowing"}
    )

    assert outcome.disposition == "preliminary_triage"
    assert outcome.result["crop"] == "Tomato"
    assert len(outcome.local_candidates) == 2
    assert [event["node"] for event in outcome.trace] == [
        "intake",
        "leaf_gate",
        "vision_models",
        "evidence_retrieval",
        "finalize_local",
    ]
    json.dumps(outcome.trace)


def test_evidence_node_attaches_only_source_backed_management_claims():
    evidence = {
        "id": "approved-tomato-source",
        "title": "Reviewed tomato guidance",
        "summary": "Reviewed summary",
        "actions": ["Keep foliage dry."],
        "source_name": "Extension service",
        "url": "https://extension.example.edu/tomato",
        "corpus_version": "test-corpus-v1",
    }
    workflow = PlantTriageWorkflow(
        make_tools(retrieve_evidence=lambda crop, condition, location: [evidence])
    )

    outcome = workflow.run(b"image", "image/jpeg", context={"location": "Nairobi"})

    assert outcome.result["evidence"] == [evidence]
    assert outcome.result["management_claims"] == [
        {
            "text": "Keep foliage dry.",
            "source_ids": ["approved-tomato-source"],
            "source_name": "Extension service",
            "url": "https://extension.example.edu/tomato",
        }
    ]
    assert outcome.trace[-2]["node"] == "evidence_retrieval"
    assert outcome.trace[-2]["status"] == "found"


def test_evidence_failure_omits_treatment_claims_and_continues_safely():
    def fail(*_args):
        raise RuntimeError("corpus unavailable")

    workflow = PlantTriageWorkflow(make_tools(retrieve_evidence=fail))

    outcome = workflow.run(b"image", "image/jpeg")

    assert outcome.disposition == "preliminary_triage"
    assert outcome.result["management_claims"] == []
    assert "evidence library was unavailable" in outcome.result["warning"]
    assert outcome.trace[-2]["status"] == "error"


def test_ai_node_retries_once_then_returns_structured_result():
    calls = {"ai": 0}

    def diagnose(*_args):
        calls["ai"] += 1
        if calls["ai"] == 1:
            raise ConnectionError("temporary")
        return SimpleNamespace(
            plant_name="Cassava",
            likely_condition="Possible mosaic disease",
            confidence_level="medium",
            summary="Cautious assessment",
            visible_observations=["Mottling"],
            possible_causes=["Possible viral disease"],
            recommended_next_steps=["Seek extension review"],
            uncertainty_note="Image-only assessment",
        )

    workflow = PlantTriageWorkflow(
        make_tools(
            predict_original=lambda _image: Prediction("Tomato___healthy", 0.20),
            predict_registered=lambda _image: [],
            ai_available=lambda: True,
            diagnose_ai=diagnose,
        )
    )
    outcome = workflow.run(
        b"image", "image/jpeg", context={"reported_crop": "Cassava", "symptoms": "Mottling"}
    )

    assert calls["ai"] == 2
    assert outcome.result["source"] == "AI-assisted fallback"
    assert outcome.result["crop"] == "Cassava"
    assert "Seek extension review" not in outcome.result["actions"]
    assert outcome.result["management_claims"] == []
    attempts = [event for event in outcome.trace if event["node"] == "ai_assessment"]
    assert [event["status"] for event in attempts] == ["retry", "ok"]


def test_ai_failure_after_bounded_retries_falls_back_to_cautious_local_result():
    calls = {"ai": 0}

    def fail(*_args):
        calls["ai"] += 1
        raise TimeoutError("unavailable")

    workflow = PlantTriageWorkflow(
        make_tools(
            predict_original=lambda _image: Prediction("Tomato___healthy", 0.20),
            predict_registered=lambda _image: [],
            ai_available=lambda: True,
            diagnose_ai=fail,
        ),
        ai_max_attempts=2,
    )
    outcome = workflow.run(
        b"image", "image/jpeg", context={"reported_crop": "Tomato", "symptoms": "Yellowing"}
    )

    assert calls["ai"] == 2
    assert outcome.disposition == "preliminary_triage"
    assert "bounded retries" in outcome.result["warning"]
    assert outcome.errors and outcome.errors[0].startswith("ai_assessment:")


def test_vision_tool_failure_returns_safe_escalation_without_diagnosis():
    def fail(_image):
        raise RuntimeError("checkpoint unavailable")

    workflow = PlantTriageWorkflow(make_tools(predict_original=fail))
    outcome = workflow.run(b"image", "image/jpeg")

    assert outcome.disposition == "escalate_human_or_lab"
    assert outcome.result["crop"] == "Unknown"
    assert outcome.result["disease"] == "Unable to assess safely"
    assert outcome.errors and outcome.errors[0].startswith("vision_models:")
    assert outcome.trace[-1]["node"] == "safe_failure"


def test_uncertain_result_requests_only_missing_critical_context():
    workflow = PlantTriageWorkflow(
        make_tools(
            predict_original=lambda _image: Prediction("Tomato___healthy", 0.20),
            predict_registered=lambda _image: [],
        )
    )
    outcome = workflow.run(b"image", "image/jpeg", context={"reported_crop": "Tomato"})

    assert outcome.disposition == "request_better_evidence"
    assert outcome.missing_context == ["symptoms"]
    assert outcome.result["source"] == "Plant AI intake agent"
    assert outcome.result["actions"] == [
        "Describe what changed, where it appears, and whether it is spreading."
    ]
    assert outcome.trace[-1]["node"] == "request_context"


def test_relevant_history_qualifies_repeated_condition_without_exposing_content_in_trace():
    workflow = PlantTriageWorkflow(make_tools())
    context = {
        "reported_crop": "Tomato",
        "history": [
            {
                "record_id": 9,
                "crop": "Tomato",
                "condition": "Healthy",
                "source": "Previous model",
                "scanned_at": "2026-08-20T10:00:00",
            }
        ],
    }
    outcome = workflow.run(b"image", "image/jpeg", context=context)

    assert outcome.memory_count == 1
    assert "1 previous Tomato record" in outcome.result["history_note"]
    assert "similar condition" in outcome.result["warning"]
    rendered_trace = json.dumps(outcome.trace)
    assert "record_id" not in rendered_trace
    assert "2026-08-20" not in rendered_trace
