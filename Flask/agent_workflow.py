from __future__ import annotations

from dataclasses import dataclass
import operator
import time
from typing import Annotated, Any, Callable, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from model import Prediction


Disposition = Literal[
    "reject_non_plant",
    "request_better_evidence",
    "preliminary_triage",
    "escalate_human_or_lab",
]


class TraceEvent(TypedDict, total=False):
    sequence: int
    node: str
    status: str
    detail: str
    duration_ms: float
    attempt: int


class TriageState(TypedDict, total=False):
    image_bytes: bytes
    mime_type: str
    force_ai: bool
    context: dict[str, Any]
    leaf_is_valid: bool
    leaf_confidence: float
    local_candidates: list[tuple[str, Prediction]]
    selected_source: str
    selected_prediction: Prediction
    ai_diagnosis: Any
    ai_requested: bool
    ai_failed: bool
    errors: Annotated[list[str], operator.add]
    trace: Annotated[list[TraceEvent], operator.add]
    disposition: Disposition
    result: dict[str, Any]


@dataclass(frozen=True)
class WorkflowTools:
    validate_leaf: Callable[[bytes], Any]
    predict_original: Callable[[bytes], Prediction]
    predict_registered: Callable[[bytes], list[tuple[str, Prediction]]]
    select_candidate: Callable[[bytes, list[tuple[str, Prediction]]], tuple[str, Prediction]]
    build_local_result: Callable[[Prediction, str], dict[str, Any]]
    format_model_votes: Callable[[list[tuple[str, Prediction]]], list[dict[str, str]]]
    local_comparison_note: Callable[[Prediction, bool], str]
    ai_available: Callable[[], bool]
    diagnose_ai: Callable[[bytes, str], Any]
    local_confidence_threshold: float


@dataclass(frozen=True)
class WorkflowOutcome:
    disposition: Disposition
    result: dict[str, Any]
    trace: list[TraceEvent]
    errors: list[str]
    local_candidates: list[tuple[str, Prediction]]
    selected_prediction: Prediction | None
    leaf_confidence: float | None


class PlantTriageWorkflow:
    """Explicit orchestration around Plant AI's existing inference tools."""

    def __init__(self, tools: WorkflowTools, *, ai_max_attempts: int = 2) -> None:
        self.tools = tools
        self.ai_max_attempts = max(1, ai_max_attempts)
        self.graph = self._build_graph()

    @staticmethod
    def _event(node: str, status: str, detail: str, started: float, **extra: Any) -> TraceEvent:
        return {
            "node": node,
            "status": status,
            "detail": detail,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            **extra,
        }

    def _intake(self, state: TriageState) -> dict[str, Any]:
        started = time.perf_counter()
        if not state.get("image_bytes") or not state.get("mime_type"):
            return {
                "errors": ["intake: missing validated image or MIME type"],
                "trace": [self._event("intake", "error", "Validated image input is missing.", started)],
            }
        return {
            "context": dict(state.get("context") or {}),
            "trace": [self._event("intake", "ok", "Validated image and available context accepted.", started)],
        }

    def _leaf_gate(self, state: TriageState) -> dict[str, Any]:
        started = time.perf_counter()
        if state.get("errors"):
            return {"trace": [self._event("leaf_gate", "skipped", "Intake failed.", started)]}
        try:
            validation = self.tools.validate_leaf(state["image_bytes"])
            return {
                "leaf_is_valid": bool(validation.is_leaf),
                "leaf_confidence": float(validation.confidence),
                "trace": [
                    self._event(
                        "leaf_gate",
                        "accepted" if validation.is_leaf else "rejected",
                        f"Leaf confidence {validation.confidence:.3f}.",
                        started,
                    )
                ],
            }
        except Exception as exc:
            return {
                "errors": [f"leaf_gate: {type(exc).__name__}: {exc}"],
                "trace": [self._event("leaf_gate", "error", "Leaf validation tool failed safely.", started)],
            }

    @staticmethod
    def _after_leaf(state: TriageState) -> str:
        if state.get("errors"):
            return "safe_failure"
        return "vision_models" if state.get("leaf_is_valid") else "finalize_rejection"

    def _vision_models(self, state: TriageState) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            candidates = [("Original ResNet34 model", self.tools.predict_original(state["image_bytes"]))]
            candidates.extend(self.tools.predict_registered(state["image_bytes"]))
            if not candidates:
                raise RuntimeError("No vision model produced a candidate")
            source, prediction = self.tools.select_candidate(state["image_bytes"], candidates)
            needs_ai = bool(state.get("force_ai")) or prediction.confidence < self.tools.local_confidence_threshold
            return {
                "local_candidates": candidates,
                "selected_source": source,
                "selected_prediction": prediction,
                "ai_requested": needs_ai,
                "trace": [
                    self._event(
                        "vision_models",
                        "ok",
                        f"Compared {len(candidates)} models; selected {source} at {prediction.confidence:.3f}.",
                        started,
                    )
                ],
            }
        except Exception as exc:
            return {
                "errors": [f"vision_models: {type(exc).__name__}: {exc}"],
                "trace": [self._event("vision_models", "error", "Vision tools failed safely.", started)],
            }

    def _after_vision(self, state: TriageState) -> str:
        if state.get("errors"):
            return "safe_failure"
        if state.get("ai_requested") and self.tools.ai_available():
            return "ai_assessment"
        return "finalize_local"

    def _ai_assessment(self, state: TriageState) -> dict[str, Any]:
        started = time.perf_counter()
        events: list[TraceEvent] = []
        last_error: Exception | None = None
        for attempt in range(1, self.ai_max_attempts + 1):
            attempt_started = time.perf_counter()
            try:
                diagnosis = self.tools.diagnose_ai(state["image_bytes"], state["mime_type"])
                events.append(
                    self._event(
                        "ai_assessment",
                        "ok",
                        "Structured AI assessment completed.",
                        attempt_started,
                        attempt=attempt,
                    )
                )
                return {"ai_diagnosis": diagnosis, "ai_failed": False, "trace": events}
            except Exception as exc:
                last_error = exc
                events.append(
                    self._event(
                        "ai_assessment",
                        "retry" if attempt < self.ai_max_attempts else "error",
                        f"Attempt {attempt} failed with {type(exc).__name__}.",
                        attempt_started,
                        attempt=attempt,
                    )
                )
        return {
            "ai_failed": True,
            "errors": [f"ai_assessment: {type(last_error).__name__}: {last_error}"],
            "trace": events
            + [self._event("ai_assessment", "fallback", "Using the cautious local fallback.", started)],
        }

    @staticmethod
    def _after_ai(state: TriageState) -> str:
        return "finalize_local" if state.get("ai_failed") else "finalize_ai"

    def _finalize_rejection(self, _state: TriageState) -> dict[str, Any]:
        started = time.perf_counter()
        return {
            "disposition": "reject_non_plant",
            "result": {},
            "trace": [self._event("finalize_rejection", "ok", "Stopped before disease classification.", started)],
        }

    def _finalize_local(self, state: TriageState) -> dict[str, Any]:
        started = time.perf_counter()
        prediction = state["selected_prediction"]
        candidates = state.get("local_candidates", [])
        result = self.tools.build_local_result(prediction, state["selected_source"])
        result["local_note"] = (
            f"Plant AI automatically compared {len(candidates)} disease models and selected "
            f"the strongest crop-aware match from {state['selected_source']}."
        )
        if state.get("ai_requested"):
            if state.get("ai_failed"):
                result["warning"] = (
                    "AI-assisted analysis failed after bounded retries. The closest local result is shown "
                    "for preliminary review only; consult a plant specialist when the image remains uncertain."
                )
            elif not self.tools.ai_available():
                if state.get("force_ai") and prediction.confidence >= self.tools.local_confidence_threshold:
                    result["warning"] = (
                        "AI-assisted analysis was requested but is not configured. The closest local-model "
                        "result is shown instead."
                    )
                else:
                    result["warning"] = (
                        "This local prediction is below the acceptance threshold and AI-assisted analysis is "
                        "not configured. Please try a clearer image or consult a plant specialist."
                    )
        result["model_votes"] = self.tools.format_model_votes(candidates)
        return {
            "disposition": "preliminary_triage",
            "result": result,
            "trace": [self._event("finalize_local", "ok", "Prepared a preliminary local report.", started)],
        }

    def _finalize_ai(self, state: TriageState) -> dict[str, Any]:
        started = time.perf_counter()
        diagnosis = state["ai_diagnosis"]
        prediction = state["selected_prediction"]
        result = {
            "source": "AI-assisted fallback",
            "is_ai": True,
            "crop": diagnosis.plant_name,
            "disease": diagnosis.likely_condition,
            "confidence_text": diagnosis.confidence_level.title(),
            "summary": diagnosis.summary,
            "observations": diagnosis.visible_observations,
            "causes": diagnosis.possible_causes,
            "actions": diagnosis.recommended_next_steps,
            "warning": diagnosis.uncertainty_note,
            "local_note": self.tools.local_comparison_note(prediction, bool(state.get("force_ai"))),
            "model_votes": self.tools.format_model_votes(state.get("local_candidates", [])),
        }
        return {
            "disposition": "preliminary_triage",
            "result": result,
            "trace": [self._event("finalize_ai", "ok", "Prepared a structured AI-assisted report.", started)],
        }

    def _safe_failure(self, state: TriageState) -> dict[str, Any]:
        started = time.perf_counter()
        result = {
            "source": "Plant AI safety workflow",
            "is_ai": False,
            "crop": "Unknown",
            "disease": "Unable to assess safely",
            "confidence_text": "Low",
            "summary": "A required analysis tool failed, so Plant AI stopped without assigning a diagnosis.",
            "observations": [],
            "causes": [],
            "actions": ["Try again with a clear image.", "Consult a local plant-health professional if symptoms are serious."],
            "warning": "No treatment decision should be based on this incomplete assessment.",
            "model_votes": self.tools.format_model_votes(state.get("local_candidates", [])),
        }
        return {
            "disposition": "escalate_human_or_lab",
            "result": result,
            "trace": [self._event("safe_failure", "ok", "Returned a safe failure without a diagnosis.", started)],
        }

    def _build_graph(self):
        builder = StateGraph(TriageState)
        builder.add_node("intake", self._intake)
        builder.add_node("leaf_gate", self._leaf_gate)
        builder.add_node("vision_models", self._vision_models)
        builder.add_node("ai_assessment", self._ai_assessment)
        builder.add_node("finalize_rejection", self._finalize_rejection)
        builder.add_node("finalize_local", self._finalize_local)
        builder.add_node("finalize_ai", self._finalize_ai)
        builder.add_node("safe_failure", self._safe_failure)
        builder.add_edge(START, "intake")
        builder.add_edge("intake", "leaf_gate")
        builder.add_conditional_edges("leaf_gate", self._after_leaf)
        builder.add_conditional_edges("vision_models", self._after_vision)
        builder.add_conditional_edges("ai_assessment", self._after_ai)
        builder.add_edge("finalize_rejection", END)
        builder.add_edge("finalize_local", END)
        builder.add_edge("finalize_ai", END)
        builder.add_edge("safe_failure", END)
        return builder.compile()

    def run(
        self,
        image_bytes: bytes,
        mime_type: str,
        *,
        force_ai: bool = False,
        context: dict[str, Any] | None = None,
    ) -> WorkflowOutcome:
        final = self.graph.invoke(
            {
                "image_bytes": image_bytes,
                "mime_type": mime_type,
                "force_ai": force_ai,
                "context": context or {},
                "errors": [],
                "trace": [],
            },
            config={"recursion_limit": 12},
        )
        trace = []
        for sequence, event in enumerate(final.get("trace", []), start=1):
            trace.append({"sequence": sequence, **event})
        return WorkflowOutcome(
            disposition=final["disposition"],
            result=final.get("result", {}),
            trace=trace,
            errors=final.get("errors", []),
            local_candidates=final.get("local_candidates", []),
            selected_prediction=final.get("selected_prediction"),
            leaf_confidence=final.get("leaf_confidence"),
        )
