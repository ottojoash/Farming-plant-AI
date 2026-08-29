# Stage 2 orchestration results: plant-ai-triage-v1

This experiment isolates the LangGraph orchestration layer. Both systems used
the same local models, thresholds, frozen case IDs, offline OpenCLIP cache, and
no LLM calls. Complete agent output is in
[`results/agent-orchestration-v1.json`](results/agent-orchestration-v1.json).

## Comparison

| Measure | Frozen baseline | Agent orchestration | Change |
| --- | ---: | ---: | ---: |
| Correct and safe triage | 4/13 (30.8%) | 4/13 (30.8%) | 0 cases |
| Crop accuracy | 44.4% | 44.4% | 0.0 pp |
| Condition accuracy | 44.4% | 44.4% | 0.0 pp |
| Plant-gate balanced accuracy | 83.3% | 83.3% | 0.0 pp |
| Critical-safety-violation cases | 7/13 | 7/13 | 0 cases |
| Median per-case latency | 0.611 s | 0.622 s | +0.011 s |
| p95 per-case latency | 8.420 s | 8.656 s | +0.236 s |
| Cold startup | 26.339 s | 26.072 s | -0.267 s |
| Total run | 42.190 s | 42.677 s | +0.487 s |
| External API cost | USD 0.00 | USD 0.00 | USD 0.00 |
| Cases with structured workflow trace | 0/13 | 13/13 | +13 cases |

Timing differences at this scale are run noise and are not claimed as an
improvement or regression.

## What improved

- Every scan follows an explicit typed state graph.
- Non-plants stop before disease classification.
- All local models remain visible as tool evidence.
- Optional AI calls have two bounded attempts and a cautious fallback.
- Required-tool errors produce `escalate_human_or_lab` rather than an invented
  diagnosis or unhandled HTTP error.
- Every evaluated run records node sequence, status, sanitized detail, duration,
  and attempt number without copying raw image bytes or credentials.
- Evaluation is isolated from MariaDB and from model-hub network latency.

## What did not improve

The graph uses the same image evidence and selection rule as the baseline, so it
made the same crop/condition mistakes and showed the same uncited static
guidance. A workflow framework cannot compensate for missing field context,
uncalibrated cross-model confidence, absent evidence retrieval, or lack of an
independent verifier.

## Decision

Keep the orchestration because it provides controlled branching, safe failure,
and inspectable trajectories required for the next stages. Do not claim an
accuracy improvement from this change. Issues #6, #7, and #8 must demonstrate
measured gains from context/memory, approved evidence, and verification.
