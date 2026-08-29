# Clean-clone reproducibility

## Supported environment

- Python 3.11 (the committed lock snapshot) or Python 3.12 with the bounded
  requirements file.
- Windows PowerShell, macOS, and Linux are supported by the Python commands;
  the CUDA requirements file is optional and GPU-specific.
- About 1 GB free disk for dependencies and the cached OpenCLIP weights, plus
  dataset space if the evaluation cases are prepared.
- No MariaDB, OpenAI key, or Flutterwave key is needed for the smoke test or
  offline baseline/agent evaluation.

## Minimal clean-clone path

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r Flask\requirements-lock-py311.txt
python scripts\smoke_test.py
python -m pytest Flask\tests training\tests evaluation\tests -q
```

The lock file records the verified Python 3.11 environment used for the
competition branch. The broader requirements file is the portable fallback for
other supported Python versions.

## Representative evaluation

Prepare the CC BY datasets using the commands in
[`evaluation/README.md`](../../evaluation/README.md), then run the frozen v1
manifest or evidence-aware v2 manifest. The first run may verify/download
OpenCLIP weights; evaluation adapters set `HF_HUB_OFFLINE=1` after startup.
Results include the exact git commit, configuration, content hashes, latency,
and external cost.

## Secrets, generated data, and licenses

`.env`, databases, model caches, raw/processed datasets, and generated result
directories are ignored by Git. Copy `.env.example` only for local development
and replace every placeholder before enabling services. Never commit a model
credential, MariaDB password, OpenAI key, Flutterwave secret, user record, or
uploaded image. See `DATASETS.md`, `training/datasets.json`, and the evaluation
manifests for dataset source and license metadata.

The application can use MariaDB/MySQL in production or SQLite for local
development. Existing installations receive additive scan-record columns at
startup; the smoke test uses an isolated in-memory database.
