"""Run a dependency/database-free application smoke test.

Usage from the repository root:
    python scripts/smoke_test.py
"""

from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
FLASK_DIR = ROOT / "Flask"
sys.path.insert(0, str(FLASK_DIR))

# Keep the smoke test self-contained and secret-free. It exercises app startup,
# schema creation, and the health contract without downloading a dataset or
# calling the optional AI service.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ALLOW_DATABASE_FALLBACK"] = "false"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ.pop("OPENAI_API_KEY", None)

from app import create_app  # noqa: E402


application = create_app(
    {
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
    }
)

with application.test_client() as client:
    response = client.get("/health")
    if response.status_code != 200:
        raise SystemExit(f"Smoke test failed: HTTP {response.status_code}")
    payload = response.get_json() or {}
    required = {"status", "local_model", "leaf_validator", "agent_workflow", "database"}
    missing = required - payload.keys()
    if missing or payload.get("status") != "ok" or payload.get("agent_workflow") != "ready":
        raise SystemExit(f"Smoke test failed: missing/invalid health fields: {sorted(missing)}")

print("Plant AI smoke test passed: startup, SQLite schema, and /health are ready.")
