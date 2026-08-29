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
| Runtime per evaluated case | Median 0.655 seconds; p95 8.945 seconds; cold startup 25.058 seconds |
| External API cost | USD 0.00 (AI fallback disabled) |

The regression-suite result proves that the existing application behavior passed
its automated tests. It is not an accuracy or safety result.

Full evaluation details: [`BASELINE_RESULTS_V1.md`](BASELINE_RESULTS_V1.md) and
[`results/baseline-v1.json`](results/baseline-v1.json).

## 2026-08-29 - Freeze evaluation v1 and measure the local baseline

- Commit/configuration: evaluation runner `689ba0b`; application reference
  `pre-agentic-hackathon-baseline` (`adaef21`); AI fallback disabled.
- Hypothesis: the existing regression tests do not demonstrate reliable and safe
  field triage.
- Change: added a versioned 13-case manifest, deterministic safety controls,
  normalized output contract, baseline adapter, and metric scorer.
- Evaluation dataset version: `plant-ai-triage-v1`.
- Primary metric result: 4/13 (30.8%) correct and safe cases.
- Secondary results: 44.4% crop accuracy, 44.4% condition accuracy, 83.3%
  plant-gate balanced accuracy, and 53.8% critical-safety-violation case rate.
- Human time, runtime, and API cost: human time not measured; 0.655-second
  median and 8.945-second p95 per-case latency; USD 0.00 external API cost.
- Regressions/failures: a generated leaf drawing was classified as blueberry; a
  blurred tomato image was classified as corn; six cases showed uncited static
  management guidance; a required human-review gate was absent.
- Decision: keep the harness and frozen cases. Target at least 9/13 safe/correct
  cases and zero critical pesticide or definitive-diagnosis violations.
- What we learned: automatic multi-model comparison is not sufficient when
  independently trained confidence scores compete, and a semantic leaf gate can
  still accept leaf-shaped artwork. Safety and evidence must be explicit stages.

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
