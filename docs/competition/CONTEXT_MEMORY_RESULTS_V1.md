# Context and memory evaluation v1

This experiment evaluates the Issue #6 intake and plant-history implementation
against the unchanged `plant-ai-triage-v1` cases. The optional AI fallback was
disabled, as in the baseline and orchestration experiments.

## Result

| Metric | Orchestration | Context/memory | Change |
| --- | ---: | ---: | ---: |
| Correct-and-safe cases | 4/13 (30.8%) | 4/13 (30.8%) | 0 |
| Crop accuracy | 44.4% | 44.4% | 0 points |
| Condition accuracy | 44.4% | 44.4% | 0 points |
| Safe-abstention precision | 100.0% | 50.0% | -50 points |
| Safe-abstention recall | 50.0% | 50.0% | 0 points |
| Critical-safety-violation rate | 53.8% | 53.8% | 0 points |
| Median per-case latency | 0.622 s | 0.725 s | +0.103 s |
| p95 per-case latency | 8.656 s | 8.101 s | -0.555 s |

Configuration: application commit `c357c67`, local confidence threshold 0.75,
leaf threshold 0.60, offline model cache, external API cost USD 0.00.

Machine-readable output:
[`results/agent-context-memory-v1.json`](results/agent-context-memory-v1.json).

## Observed behavior

- The potato and tomato examples had local confidence below 0.75. Because their
  manifests supplied a crop but no symptom description, the intake agent asked
  only for `symptoms` and returned `request_better_evidence`.
- The blurred tomato control remained a preliminary corn diagnosis because its
  selected model confidence was 0.794, above the threshold. This shows that raw
  classifier confidence is not calibrated well enough to decide image quality.
- The v1 cases do not carry authenticated account history, so the benchmark did
  not exercise recurrence memory. Dedicated workflow and route tests verify
  crop relevance, ownership, paid-plan access, the five-record bound, and the
  recurrence warning.
- Existing uncited static management text still caused six unsupported-claim
  violations. Evidence retrieval remains necessary before these claims can be
  presented safely.

## Decision

Keep the context and owned-memory infrastructure because it establishes useful
control, privacy, and continuity behavior and passes the application suite. Do
not claim an improvement in the primary quality metric. Issue #7 should replace
static management text with approved, cited evidence; Issue #8 must calibrate
uncertainty independently of the winning classifier's confidence.

The next evaluation-manifest revision should add an authenticated longitudinal
case and separate image-quality expectations so that memory and clarification
quality can be scored directly.
