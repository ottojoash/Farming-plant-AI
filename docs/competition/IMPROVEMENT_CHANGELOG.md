# Plant AI competition Improvement Changelog

This changelog records measured changes made after the frozen pre-hackathon
baseline. Results must use the same versioned evaluation cases before they are
used in competition claims.

## Baseline - frozen 2026-08-29

| Field | Value |
| --- | --- |
| Reference | `pre-agentic-hackathon-baseline` (`adaef21`) |
| Architecture | Leaf gate -> three local classifiers -> crop-aware selection -> optional single-call AI fallback |
| Regression suite | 37 passed in 65.00s on Python 3.11.9 |
| Primary metric | 4/13 correct and safe cases (30.8%; 95% Wilson interval 12.7%-57.6%) |
| Versioned evaluation cases | `plant-ai-triage-v1` (13 cases) |
| Human time | Not measured |
| Runtime per evaluated case | Median 0.611 seconds; p95 8.420 seconds; cold startup 26.339 seconds |
| External API cost | USD 0.00 (AI fallback disabled) |

The regression-suite result proves that the existing application behavior passed
its automated tests. It is not an accuracy or safety result.

Full evaluation details: [`BASELINE_RESULTS_V1.md`](BASELINE_RESULTS_V1.md) and
[`results/baseline-v1.json`](results/baseline-v1.json).

## 2026-08-29 - Freeze evaluation v1 and measure the local baseline

- Commit/configuration: evaluation runner `ebd67c2`; application reference
  `pre-agentic-hackathon-baseline` (`adaef21`); AI fallback disabled.
- Hypothesis: the existing regression tests do not demonstrate reliable and safe
  field triage.
- Change: added a versioned 13-case manifest, deterministic safety controls,
  normalized output contract, baseline adapter, and metric scorer.
- Evaluation dataset version: `plant-ai-triage-v1`.
- Primary metric result: 4/13 (30.8%) correct and safe cases.
- Secondary results: 44.4% crop accuracy, 44.4% condition accuracy, 83.3%
  plant-gate balanced accuracy, and 53.8% critical-safety-violation case rate.
- Human time, runtime, and API cost: human time not measured; 0.611-second
  median and 8.420-second p95 per-case latency; USD 0.00 external API cost.
- Regressions/failures: a generated leaf drawing was classified as blueberry; a
  blurred tomato image was classified as corn; six cases showed uncited static
  management guidance; a required human-review gate was absent.
- Decision: keep the harness and frozen cases. Target at least 9/13 safe/correct
  cases and zero critical pesticide or definitive-diagnosis violations.
- What we learned: automatic multi-model comparison is not sufficient when
  independently trained confidence scores compete, and a semantic leaf gate can
  still accept leaf-shaped artwork. Safety and evidence must be explicit stages.

## 2026-08-29 - Add typed LangGraph orchestration

- Commit/configuration: application `64c40a9`; offline evaluation configuration
  `ebd67c2`; AI fallback disabled.
- Hypothesis: explicit conditional orchestration will improve control,
  observability, and safe failure, but will not by itself fix model quality.
- Change: introduced typed shared state, eight graph nodes, conditional routing,
  two bounded AI attempts, safe tool-failure escalation, and sanitized traces.
- Evaluation dataset version: `plant-ai-triage-v1`.
- Primary metric result: 4/13 (30.8%), identical to baseline.
- Secondary results: crop and condition accuracy remained 44.4%; all 13 agent
  cases produced structured traces; safety-violation rate remained 53.8%.
- Human time, runtime, and API cost: human time not measured; 0.622-second
  median and 8.656-second p95 per-case latency; USD 0.00 external API cost.
- Regressions/failures: no quality regression; the first pre-fix run revealed a
  model-hub/cache delay through a 1,895-second leaf-gate trace. Evaluation now
  uses the verified local model cache without network checks.
- Decision: keep the orchestration foundation. Do not claim a quality gain.
- What we learned: an agent framework makes failures inspectable and containable,
  but context, evidence retrieval, and independent verification are the parts
  expected to improve correct-and-safe triage.

Full comparison: [`AGENT_ORCHESTRATION_RESULTS_V1.md`](AGENT_ORCHESTRATION_RESULTS_V1.md).

## 2026-08-29 - Add context-aware intake and owned plant memory

- Commit/configuration: application `c357c67`; AI fallback disabled; local
  confidence threshold 0.75.
- Hypothesis: targeted context requests and relevant prior records will make
  uncertain triage safer and add continuity without exposing account data.
- Change: added bounded field context, a low-confidence clarification node,
  paid-plan retrieval of the five newest owned crop records, recurrence
  qualification, and sanitized trace summaries.
- Evaluation dataset version: `plant-ai-triage-v1`.
- Primary metric result: 4/13 (30.8%), unchanged from orchestration.
- Secondary results: crop and condition accuracy remained 44.4%; safe-abstention
  precision fell from 100.0% to 50.0%, recall remained 50.0%, and the critical
  safety-violation rate remained 53.8%.
- Human time, runtime, and API cost: human time not measured; 0.725-second
  median and 8.101-second p95 per-case latency; USD 0.00 external API cost.
- Regressions/failures: two low-confidence disease cases requested symptoms,
  but the blurred control remained an overconfident corn prediction at 79.4%.
  The frozen manifest contains no authenticated longitudinal history case.
- Decision: keep the privacy and continuity controls, but do not claim a quality
  gain. Add evidence retrieval and independent uncertainty checks next.
- What we learned: classifier confidence alone cannot identify every poor image,
  and memory requires an explicit longitudinal evaluation case to measure its
  effect rather than only its access-control correctness.

Full comparison: [`CONTEXT_MEMORY_RESULTS_V1.md`](CONTEXT_MEMORY_RESULTS_V1.md).

## 2026-08-29 - Add versioned agricultural evidence retrieval

- Commit/configuration: application `6a204bb`; evidence-aware evaluation
  manifest `plant-ai-triage-v2-evidence`; AI fallback disabled.
- Hypothesis: exact crop/condition retrieval from reviewed extension and IPM
  sources will remove unsupported management claims and improve safe triage.
- Change: added a hashed local corpus, deterministic LangGraph retrieval node,
  claim-level source IDs/links, regional scope notes, paid-record provenance,
  additive MariaDB/SQLite columns, and unsupported-crop fallback. Removed the
  legacy unscoped known-class management block from final reports; it is now
  omitted unless claim-level approved evidence is available.
- Evaluation dataset version: `plant-ai-triage-v2-evidence` (same 13 assets and
  labels as v1, with approved source IDs added to expected disease cases).
- Primary metric result: 5/13 (38.5%), up from the comparable baseline's 4/13
  (30.8%).
- Secondary results: crop and condition accuracy stayed at 44.4%; critical
  safety-violation cases fell from 7 to 4; unsupported management violations
  fell from 6 to 2; supported-management-claim rate reached 50.0%.
- Human time, runtime, and API cost: human time not measured; 0.720-second
  median and 8.774-second p95 per-case latency; USD 0.00 external API cost.
- Regressions/failures: two misidentified cases retrieved wrong-scope evidence,
  which the case-specific approval list correctly rejected. Vision confidence
  and image-quality calibration remain unresolved.
- Decision: keep the evidence retrieval layer. Proceed to independent
  verification and human approval before broadening the corpus.
- What we learned: claim-level provenance and omission on unsupported matches
  materially reduce safety violations, but retrieval cannot repair a wrong
  diagnosis or uncalibrated confidence.

Full comparison: [`EVIDENCE_RETRIEVAL_RESULTS_V2.md`](EVIDENCE_RETRIEVAL_RESULTS_V2.md).

## 2026-08-29 - Add verification and human approval checkpoints

- Commit/configuration: application verification stage on the `agent` branch;
  local confidence threshold 0.75 and cross-model crop disagreement margin 0.15.
- Hypothesis: explicit verification reasons and a pending human checkpoint will
  prevent reports from being mistaken for autonomous treatment decisions.
- Change: added a post-retrieval verification node, visible pending checkpoint
  in anonymous and signed-in reports, clarification/safe-failure checkpoint
  states, and trace/evaluation fields.
- Evaluation dataset version: `plant-ai-triage-v2-evidence` (same 13 assets).
- Primary quality metric: unchanged by design; this stage measures control and
  review visibility rather than classifier accuracy.
- Safety controls: non-plant rejection, context abstention, source-backed-only
  actions, and human-review reasons are all covered by automated tests.
- Regressions/failures: thresholds are not calibrated probabilities and the
  current benchmark has no interactive reviewer, so approval completion and
  handling time are not measured.
- Decision: keep the gate and require reviewer trajectory coverage before any
  consequential-action integration.
- What we learned: review state must be explicit in both the UI and trace; a
  warning string alone is not an auditable approval boundary.

Verification artifact: [`results/agent-verification-v2.json`](results/agent-verification-v2.json).

## Experiment entries

Add one entry per material iteration using this template:

```markdown
## YYYY-MM-DD - Short experiment name

- Commit/configuration:
- Hypothesis:
- Change:
- Evaluation dataset version:
- Primary metric result:
- Secondary results (accuracy, safe abstention, unsupported claims):
- Human time, runtime, and API cost:
- Regressions/failures:
- Decision: keep, revise, or remove
- What we learned:
```
