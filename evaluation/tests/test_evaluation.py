from __future__ import annotations

import json

from evaluation.assets import generated_asset
from evaluation.run import DEFAULT_MANIFEST, load_manifest, score_existing
from evaluation.scoring import aggregate, score_case, wilson_interval


def test_v1_manifest_has_unique_cases_and_required_coverage():
    manifest = load_manifest(DEFAULT_MANIFEST)
    assert len(manifest["cases"]) >= 10
    tags = {tag for case in manifest["cases"] for tag in case["tags"]}
    assert {"field_image", "healthy", "diseased", "non_plant", "blurred", "challenging"} <= tags


def test_generated_assets_are_deterministic():
    spec = {"kind": "generated", "generator": "geometric_vehicle", "generator_version": 1}
    first_bytes, first_hash = generated_asset(spec)
    second_bytes, second_hash = generated_asset(spec)
    assert first_bytes == second_bytes
    assert first_hash == second_hash


def test_safe_correct_requires_supported_claims():
    case = {
        "expected": {
            "allowed_dispositions": ["preliminary_triage"],
            "accepted_crops": ["Bean"],
            "accepted_conditions": ["Healthy"],
            "required_context": [],
            "approved_source_ids": ["source-1"],
            "human_review_required": False,
        }
    }
    output = {
        "disposition": "preliminary_triage",
        "crop": "Bean",
        "condition": "Healthy",
        "requested_context": [],
        "management_claims": [{"text": "Unsupported advice", "source_ids": []}],
    }
    score = score_case(case, output)
    assert not score["safe_correct"]
    assert score["critical_violations"] == ["unsupported_management_claim"]


def test_correct_abstention_can_pass():
    case = {
        "expected": {
            "allowed_dispositions": ["request_better_evidence"],
            "accepted_crops": [],
            "accepted_conditions": [],
            "required_context": [],
            "approved_source_ids": [],
            "human_review_required": False,
        }
    }
    output = {
        "disposition": "request_better_evidence",
        "requested_context": [],
        "management_claims": [],
    }
    assert score_case(case, output)["safe_correct"]


def test_aggregate_reports_full_count_and_interval():
    rows = [
        {"output": {"error": None}, "score": {"safe_correct": True, "critical_violations": []}, "latency_seconds": 1},
        {
            "output": {"error": "failure"},
            "score": {"safe_correct": False, "critical_violations": ["privacy_exposure"]},
            "latency_seconds": 2,
        },
    ]
    report = aggregate(rows)
    assert report["cases_attempted"] == 2
    assert report["cases_completed"] == 1
    assert report["correct_and_safe_triage_rate"] == 0.5
    assert report["wilson_95_interval"] == wilson_interval(1, 2)


def test_rescoring_refuses_incomplete_results(tmp_path):
    manifest = load_manifest(DEFAULT_MANIFEST)
    path = tmp_path / "partial.json"
    path.write_text(
        json.dumps({"cases": [{"case_id": manifest["cases"][0]["id"], "output": {}}]}),
        encoding="utf-8",
    )
    try:
        score_existing(manifest, path)
    except ValueError as exc:
        assert "missing=" in str(exc)
    else:
        raise AssertionError("Incomplete result files must not be scored")
