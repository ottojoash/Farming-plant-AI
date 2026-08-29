from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


def _load_agent(project_root: Path):
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["ALLOW_DATABASE_FALLBACK"] = "false"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ.pop("ADMIN_PASSWORD", None)
    flask_dir = project_root / "Flask"
    if str(flask_dir) not in sys.path:
        sys.path.insert(0, str(flask_dir))
    import app as agent_app
    from entitlements import details_as_text

    # The Stage 2 comparison is local-only and deterministic. Later experiments
    # can opt into a versioned LLM configuration and record its cost separately.
    agent_app.is_ai_available = lambda: False
    return agent_app, details_as_text


class AgentWorkflowAdapter:
    name = "langgraph-plant-triage-workflow"
    application_reference = "agent branch Stage 2 workflow"

    def __init__(self, project_root: Path) -> None:
        self.app, self.details_as_text = _load_agent(project_root)

    def run(self, image_bytes: bytes, case: dict[str, Any]) -> dict[str, Any]:
        outcome = self.app.TRIAGE_WORKFLOW.run(
            image_bytes,
            "image/png" if case["asset"]["kind"] in {"generated", "blurred_file"} else "image/jpeg",
            context=case.get("context", {}),
        )
        result = outcome.result
        management_claims = []
        if result.get("details_html"):
            management_claims.append(
                {"text": self.details_as_text(result["details_html"]) or "", "source_ids": []}
            )
        return {
            "disposition": outcome.disposition,
            "crop": result.get("crop"),
            "condition": result.get("disease"),
            "confidence": (
                outcome.selected_prediction.confidence if outcome.selected_prediction else None
            ),
            "requested_context": outcome.missing_context,
            "management_claims": management_claims,
            "is_definitive": False,
            "pesticide_details": [],
            "human_review_present": outcome.disposition == "escalate_human_or_lab",
            "privacy_violation": False,
            "external_cost_usd": 0.0,
            "model_votes": result.get("model_votes", []),
            "workflow_trace": outcome.trace,
            "workflow_errors": outcome.errors,
        }
