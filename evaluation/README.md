# Plant AI competition evaluation

The evaluation harness compares the frozen baseline and future agent versions on
the same case IDs. Version 1 contains attributable held-out field images plus
deterministic safety controls. Images from the repository's legacy
`test_images/` directories are intentionally excluded because their provenance
and redistribution terms are not documented.

## Dataset sources

| Dataset | Role | Licence | Acquisition |
| --- | --- | --- | --- |
| PlantDoc | Multi-crop field-image cases | CC BY 4.0 | `python training\download_datasets.py plantdoc` |
| Tanzania common beans | Bean specialist cases | CC BY 4.0 | `python training\download_datasets.py beans_tanzania` |
| Plant AI deterministic controls | Non-plant, drawing, and blur safety cases | Project MIT licence | Generated locally by `evaluation/assets.py` |

Prepare the external datasets from the repository root:

```powershell
python training\download_datasets.py plantdoc
python training\prepare_dataset.py plantdoc
python training\download_datasets.py beans_tanzania
python training\prepare_dataset.py beans_tanzania
```

For a clean-clone smoke check that does not need either dataset or private
credentials, run `python scripts\smoke_test.py` from the repository root. It
starts the app against an in-memory SQLite database and verifies `/health`.

The manifest references exact held-out paths and SHA-256 digests. Preparation is
deterministic, so a changed or missing asset causes a visible error instead of
silently changing the benchmark. The evidence-aware comparison uses
`cases/v2-evidence-manifest.json`; it keeps the same image assets and labels as
v1 while adding case-specific approved source IDs for
`Flask/evidence/corpus-v1.json`. The v1 manifest remains frozen for
pre-evidence comparisons.

## Validate the case package

```powershell
python -m evaluation.run --validate-only
```

## Run the frozen local baseline

Run this command from a checkout of `pre-agentic-hackathon-baseline` after copying
the `evaluation/` directory from the competition branch, or use a worktree. The
adapter intentionally disables the optional OpenAI fallback so the local
baseline is repeatable and has no API cost.

```powershell
python -m evaluation.run --adapter baseline --output evaluation\results\baseline-v1.json
```

The real leaf gate may download its configured OpenCLIP weights on first use.
After acquisition, both evaluation adapters set `HF_HUB_OFFLINE=1` so a network
or model-hub delay cannot silently distort the comparison.
The runner records every case, failure, latency, selected model, model votes,
component checks, critical violations, the primary metric, and its 95 percent
Wilson interval.

## Score normalized output from another system

Run the current local agent workflow with structured traces:

```powershell
python -m evaluation.run --adapter agent --output evaluation\results\agent-v1.json
```

The evidence-aware v2 comparison uses the same image assets and labels with
case-specific approved source IDs:

```powershell
python -m evaluation.run --manifest evaluation\cases\v2-evidence-manifest.json --adapter agent --output agent-evidence-v2.json
```

The Stage 2 adapter disables the optional LLM call so its first comparison is
deterministic and free. Later LLM experiments must record their exact model,
prompt/configuration, token use, and external cost.

An agent runner should emit the same per-case `output` fields. Re-score it
without invoking models:

```powershell
python -m evaluation.run --score-results path\to\agent-results.json --output evaluation\results\agent-v1-scored.json
```

Do not commit generated result files until their configuration, commit, and cost
metadata have been reviewed. `evaluation/results/` is ignored by default.

## Version 1 limitations

- It is a 13-case engineering benchmark, not a statistically representative
  field study.
- PlantDoc and bean labels come from their published datasets and have not yet
  been independently re-annotated by a local plant pathologist.
- The three non-plant controls are deterministic drawings, not evidence of
  real-world non-plant rejection accuracy.
- The blurred case is a deterministic derivative, not a naturally poor upload.
- Crop/condition scoring uses accepted labels; later expert review may add
  clinically equivalent categories without changing the source images.
