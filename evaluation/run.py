from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
from typing import Any

from evaluation.assets import AssetError, materialize_asset
from evaluation.scoring import aggregate, score_case


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_ROOT / "evaluation" / "cases" / "v1" / "manifest.json"


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    case_ids = [case["id"] for case in manifest["cases"]]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Evaluation case IDs must be unique")
    if len(case_ids) < 10:
        raise ValueError("Competition evaluation manifests require at least 10 cases")
    return manifest


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _adapter(name: str):
    if name == "baseline":
        from evaluation.baseline_adapter import BaselineAdapter

        return BaselineAdapter(PROJECT_ROOT)
    raise ValueError(f"Unknown adapter: {name}")


def validate_assets(manifest: dict[str, Any]) -> list[dict[str, str]]:
    validated = []
    for case in manifest["cases"]:
        _, digest = materialize_asset(case["asset"], PROJECT_ROOT)
        validated.append({"case_id": case["id"], "content_hash": digest})
    return validated


def run_evaluation(manifest: dict[str, Any], adapter_name: str) -> dict[str, Any]:
    adapter = _adapter(adapter_name)
    started = datetime.now(timezone.utc)
    cases = []
    for case in manifest["cases"]:
        image_bytes, digest = materialize_asset(case["asset"], PROJECT_ROOT)
        before = time.perf_counter()
        try:
            output = adapter.run(image_bytes, case)
            output.setdefault("error", None)
        except Exception as exc:  # A failed case must remain visible in the report.
            output = {
                "disposition": "escalate_human_or_lab",
                "crop": None,
                "condition": None,
                "requested_context": [],
                "management_claims": [],
                "is_definitive": False,
                "pesticide_details": [],
                "human_review_present": False,
                "privacy_violation": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        latency = time.perf_counter() - before
        cases.append(
            {
                "case_id": case["id"],
                "content_hash": digest,
                "latency_seconds": latency,
                "output": output,
                "score": score_case(case, output),
            }
        )
    finished = datetime.now(timezone.utc)
    return {
        "schema_version": 1,
        "evaluation_dataset": manifest["dataset_version"],
        "system": {
            "adapter": adapter_name,
            "name": adapter.name,
            "application_reference": adapter.application_reference,
            "runner_git_commit": git_commit(),
            "configuration": {
                "ai_fallback": False,
                "leaf_validation_threshold": adapter.app.LEAF_VALIDATOR.threshold,
                "local_confidence_threshold": adapter.app.LOCAL_CONFIDENCE_THRESHOLD
            }
        },
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": (finished - started).total_seconds(),
        "cases": cases,
        "aggregate": aggregate(cases),
    }


def score_existing(manifest: dict[str, Any], result_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    by_id = {case["id"]: case for case in manifest["cases"]}
    scored = []
    for item in result["cases"]:
        case = by_id[item["case_id"]]
        updated = dict(item)
        updated["score"] = score_case(case, item["output"])
        scored.append(updated)
    result["cases"] = scored
    result["aggregate"] = aggregate(scored)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run and score the Plant AI competition evaluation")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--adapter", choices=["baseline"], default="baseline")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--score-results", type=Path)
    args = parser.parse_args()

    manifest = load_manifest(args.manifest.resolve())
    try:
        if args.validate_only:
            report: Any = {
                "dataset_version": manifest["dataset_version"],
                "assets": validate_assets(manifest),
            }
        elif args.score_results:
            report = score_existing(manifest, args.score_results.resolve())
        else:
            report = run_evaluation(manifest, args.adapter)
    except AssetError as exc:
        parser.error(str(exc))

    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
