# Evidence retrieval evaluation v2

This comparison keeps the same 13 image assets and labels as `plant-ai-triage-v1`
but adds approved source IDs to the expected disease cases. The manifest is
[`evaluation/cases/v2-evidence-manifest.json`](../../evaluation/cases/v2-evidence-manifest.json);
its corpus hash points to the reviewed local evidence collection.

## Results

| Metric | Baseline | Agent + retrieval |
| --- | ---: | ---: |
| Correct-and-safe cases | 4/13 (30.8%) | 5/13 (38.5%) |
| Crop accuracy | 44.4% | 44.4% |
| Condition accuracy | 44.4% | 44.4% |
| Critical-safety-violation cases | 7/13 (53.8%) | 4/13 (30.8%) |
| Unsupported management violations | 6 | 2 |
| Supported-management-claim rate | 0.0% | 50.0% |
| Plant-gate balanced accuracy | 83.3% | 83.3% |
| Median latency | 0.675 s | 0.720 s |
| p95 latency | 8.587 s | 8.774 s |

The agent result is [`results/agent-evidence-v2.json`](results/agent-evidence-v2.json)
and the directly comparable baseline is
[`results/baseline-evidence-v2.json`](results/baseline-evidence-v2.json).
Both used offline local models and USD 0.00 external API cost.

## Interpretation

The correct-and-safe rate increased by one case because the agent attached
approved, scope-matched guidance to the grape black-rot case while the baseline
had uncited static guidance. Unsupported management violations fell from six to
two because the agent omits guidance when a predicted crop/condition has no
approved match. The two remaining violations are intentionally visible:
misidentified apple and bean cases retrieved evidence for the wrong condition,
so the case-specific approval list rejected those claims.

This is an evidence-safety result, not a vision-accuracy result: crop and
condition accuracy did not change. Low-confidence potato and tomato cases still
request missing symptoms, and the blurred control remains overconfident. Those
problems are in scope for Issue #8's independent verification and calibration.

The v2 manifest is a new evidence-scoring view of the same assets; v1 remains
unchanged as the frozen pre-evidence comparison.
