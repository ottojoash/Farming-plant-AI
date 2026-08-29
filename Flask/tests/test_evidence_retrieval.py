from __future__ import annotations

import json

import pytest

from evidence_retrieval import EvidenceCorpusError, EvidenceRetriever


def test_exact_crop_and_condition_returns_versioned_source() -> None:
    retriever = EvidenceRetriever()

    evidence = retriever.retrieve("Tomato", "Late blight", "Nairobi, Kenya")

    assert len(evidence) == 1
    assert evidence[0]["id"] == "umn-extension-tomato-potato-late-blight"
    assert evidence[0]["url"].startswith("https://extension.umn.edu/")
    assert evidence[0]["corpus_version"] == "plant-ai-evidence-2026-08-29-v1"
    assert len(evidence[0]["corpus_sha256"]) == 64
    assert "Nairobi, Kenya" in evidence[0]["location_note"]


def test_unsupported_or_mismatched_scope_returns_no_guidance() -> None:
    retriever = EvidenceRetriever()

    assert retriever.retrieve("Cassava", "Mosaic disease") == []
    assert retriever.retrieve("Tomato", "Bean rust") == []
    assert retriever.retrieve("", "Late blight") == []


def test_invalid_or_duplicate_corpus_is_rejected(tmp_path) -> None:
    corpus = json.loads(EvidenceRetriever().corpus_path.read_text(encoding="utf-8"))
    corpus["entries"].append(dict(corpus["entries"][0]))
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(corpus), encoding="utf-8")

    with pytest.raises(EvidenceCorpusError, match="Duplicate evidence ID"):
        EvidenceRetriever(path)
