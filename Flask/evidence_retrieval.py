from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DEFAULT_CORPUS_PATH = Path(__file__).resolve().parent / "evidence" / "corpus-v1.json"


def normalize_term(value: str | None) -> str:
    return " ".join((value or "").casefold().replace("_", " ").split())


class EvidenceCorpusError(ValueError):
    pass


class EvidenceRetriever:
    """Deterministic exact-scope retrieval over a reviewed local corpus."""

    def __init__(self, corpus_path: Path = DEFAULT_CORPUS_PATH) -> None:
        self.corpus_path = corpus_path
        raw = corpus_path.read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        self.data = json.loads(raw.decode("utf-8"))
        self.corpus_version = str(self.data.get("corpus_version") or "")
        self.entries = list(self.data.get("entries") or [])
        self._validate()

    def _validate(self) -> None:
        if self.data.get("schema_version") != 1 or not self.corpus_version:
            raise EvidenceCorpusError("Evidence corpus schema or version is missing")
        identifiers: set[str] = set()
        required = {
            "id",
            "crop",
            "crop_aliases",
            "condition",
            "condition_aliases",
            "title",
            "summary",
            "actions",
            "source_name",
            "url",
            "region_scope",
            "retrieved_at",
        }
        for entry in self.entries:
            missing = required - set(entry)
            if missing:
                raise EvidenceCorpusError(f"Evidence entry is missing fields: {sorted(missing)}")
            identifier = str(entry["id"])
            if identifier in identifiers:
                raise EvidenceCorpusError(f"Duplicate evidence ID: {identifier}")
            identifiers.add(identifier)
            parsed = urlparse(str(entry["url"]))
            if parsed.scheme != "https" or not parsed.netloc:
                raise EvidenceCorpusError(f"Evidence URL must be HTTPS: {identifier}")
            if not entry["actions"]:
                raise EvidenceCorpusError(f"Evidence entry has no reviewed actions: {identifier}")

    def retrieve(
        self,
        crop: str | None,
        condition: str | None,
        location: str | None = None,
        *,
        limit: int = 2,
    ) -> list[dict[str, Any]]:
        crop_key = normalize_term(crop)
        condition_key = normalize_term(condition)
        if not crop_key or not condition_key:
            return []
        matches = []
        for entry in self.entries:
            crops = {normalize_term(item) for item in entry["crop_aliases"]}
            conditions = {normalize_term(item) for item in entry["condition_aliases"]}
            if crop_key not in crops or condition_key not in conditions:
                continue
            item = deepcopy(entry)
            item["corpus_version"] = self.corpus_version
            item["corpus_sha256"] = self.sha256
            item["location_note"] = (
                f"The user reported {location}; this source's scope is {entry['region_scope']}"
                if location
                else f"Source scope: {entry['region_scope']}"
            )
            matches.append(item)
            if len(matches) >= max(1, min(limit, 3)):
                break
        return matches


EVIDENCE_RETRIEVER = EvidenceRetriever()
