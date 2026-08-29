# Plant AI pre-hackathon baseline

This document freezes the state of Plant AI before work for the micro1 Frontier
Engineering Challenge 2026. It is the comparison point for all competition
experiments and final claims.

## Immutable reference

| Field | Value |
| --- | --- |
| Git tag | `pre-agentic-hackathon-baseline` |
| Commit | `adaef21a99c343c6ba969e7f0815e23cbc9f3671` |
| Source branch at freeze time | `test` |
| Tag created | 2026-08-29 (Africa/Nairobi) |
| Competition branch | `agent` |

To inspect the exact baseline without moving an existing working tree:

```powershell
git worktree add ..\Farming-plant-AI-baseline pre-agentic-hackathon-baseline
```

## Pre-existing-work disclosure

Everything reachable from the baseline tag existed before the competition
implementation began. This includes the web interface, plant-image checks,
classification models, optional OpenAI fallback, accounts, subscriptions,
payments, dashboards, scan history, training utilities, documentation, tests,
model checkpoints, and dataset catalogue.

Competition work begins after this tag on the `agent` branch. A feature is not
counted as a competition improvement merely because it is described differently
or exercised by a new benchmark. Each claimed improvement must link to a later
commit and a result obtained on the same versioned evaluation cases.

## Baseline user workflow

1. A visitor or signed-in user uploads a JPEG, PNG, or WebP image up to 5 MB.
2. The application validates and decodes the file.
3. An OpenCLIP zero-shot gate decides whether the image appears to contain a
   sufficiently clear plant leaf.
4. Accepted images are passed to the original ResNet34 classifier and every
   classifier registered in `Models/registry.json`.
5. A crop-aware score combines each disease confidence with OpenCLIP crop
   similarity and selects one local result.
6. If that result is below the configured threshold, or AI analysis was
   explicitly requested, one LangChain `ChatOpenAI` structured-output call can
   produce a cautious image assessment when an API key is available.
7. The result and all model votes are rendered. Usage is counted, and eligible
   paid users receive a metadata-only history record.

This is a hybrid inference pipeline, but it is not yet an agentic workflow. The
OpenAI fallback is one prompt and one response: it has no explicit plan, tool
selection, evidence retrieval, persistent task state, verification step, or
human approval gate.

## Existing components

### Image and model path

- OpenCLIP leaf/non-leaf validation with a default acceptance threshold of 0.60.
- Original ResNet34 checkpoint with 38 closed-set classes across 14 crops.
- Registered Beans MobileNetV3 model with 3 classes. Its registry metadata
  reports 0.9969 test accuracy and 0.9969 macro F1.
- Registered PlantDoc Field MobileNetV3 model with 27 classes. Its registry
  metadata reports 0.6102 test accuracy and 0.6108 macro F1.
- Automatic execution of all three disease classifiers followed by crop-aware
  routing.
- Local-result acceptance threshold of 0.75.
- Optional multimodal OpenAI fallback returning validated Pydantic fields.

Registry metrics are historical metadata, not results from the competition
benchmark. Their source test sets are different and the numbers must not be
compared directly.

### Product path

- Flask factory, upload handling, health endpoint, and server-side templates.
- Shared user/admin authentication with password hashing and CSRF protection.
- Anonymous two-scan trial and configurable free monthly allowance.
- Monthly/yearly paid plans, scan history, record detail pages, and Flutterwave
  checkout/verification integration.
- Role-aware user and administrator dashboards.
- MariaDB/MySQL support with an opt-in SQLite development fallback.

### Data and training path

- Dataset catalogue entries for beans, cassava, paddy/rice, and PlantDoc.
- Download, deterministic preparation, training, held-out evaluation, and model
  registration scripts.
- Source/licence notes in `DATASETS.md` and `training/datasets.json`.

## Baseline verification result

The existing automated suite was run without changing application behavior.

```text
Date:       2026-08-29
Platform:   Windows / PowerShell
Python:     3.11.9
Command:    .\.venv\Scripts\python.exe -m pytest Flask\tests training\tests -q --disable-warnings --durations=10
Result:     37 passed in 65.00s
Commit:     adaef21a99c343c6ba969e7f0815e23cbc9f3671
```

The suite covers Flask routes, upload validation, mocked non-leaf rejection,
automatic model scanning/routing, structured fallback escaping, account and plan
rules, Flutterwave verification behavior, dashboards, history permissions, and
training-pipeline utilities. It is a regression suite, not a field-accuracy
benchmark. Several inference dependencies are mocked, and the suite does not
establish disease accuracy, leaf-gate accuracy, calibration, human time saved,
or safety of generated recommendations.

## Known baseline limitations

### Agent design

- The LangChain path is a single `ChatOpenAI.with_structured_output` invocation.
- There is no intake agent to obtain crop, location, symptom duration, or recent
  treatment context.
- Scan history is displayed to users but is not used as agent memory.
- There is no evidence-retrieval tool or claim-to-source verification.
- There is no independent verifier, model-disagreement policy, or explicit human
  approval checkpoint before consequential treatment decisions.
- No representative agent trajectories are captured.

### Measurement

- There is no frozen, versioned evaluation set shared by baseline and final runs.
- No primary competition metric is implemented.
- The repository has no end-to-end measurements of correct safe triage,
  abstention quality, unsupported claims, human time, runtime, or API cost.
- Current sample images are not accompanied by authoritative ground truth,
  provenance, or a machine-readable evaluation manifest.

### Model and safety quality

- The original 38-class model is closed-set and can confidently map unsupported
  plants or conditions to a known label after the leaf gate accepts an image.
- OpenCLIP and confidence thresholds have not been calibrated on a documented
  representative field test set.
- Model confidence values from independently trained classifiers are not
  necessarily comparable.
- The AI fallback can provide cautious advice, but it does not retrieve or verify
  sources per diagnosis.
- Static reference summaries do not prove that a recommendation applies to the
  detected crop, region, or local pesticide registration.
- Agricultural guidance has not yet received documented qualified local review.

### Reproducibility and packaging

- Two tracked copies of the original checkpoint are about 85 MB each.
- Generated Chroma files, a notebook checkpoint, and model binaries are tracked
  even though current ignore rules exclude new copies.
- The Git object pack was about 109.68 MiB when the baseline was frozen.
- Model/dataset licensing and provenance are incomplete for a clean public
  submission.
- The dependency ranges are bounded but not locked to exact resolved versions.
- The optional AI path, MariaDB, and Flutterwave require external configuration;
  a complete judge-oriented mock/demo path does not yet exist.
- The README records that an API credential appeared in earlier Git history. The
  owner must revoke it and decide on history sanitization or a clean submission
  archive before delivery.

## Baseline reproduction

```powershell
git clone https://github.com/ottojoash/Farming-plant-AI.git
Set-Location Farming-plant-AI
git checkout pre-agentic-hackathon-baseline
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r Flask\requirements.txt
python -m pytest Flask\tests training\tests -q
```

The tests use isolated configuration and do not require production credentials.
Running the interactive application additionally requires the configuration
described in the baseline README. OpenCLIP may download its configured weights
the first time real leaf validation runs.

## Rules for future comparisons

- Run the baseline tag and final commit against identical versioned case IDs.
- Keep the primary metric definition fixed after the evaluation set is frozen.
- Record prompts, model versions, thresholds, dependency/environment details,
  runtime, external calls, and cost.
- Publish per-case outputs, not only aggregate success rates.
- Report failures, abstentions, regressions, and human interventions.
- Do not treat historical registry metrics as competition improvement evidence.
