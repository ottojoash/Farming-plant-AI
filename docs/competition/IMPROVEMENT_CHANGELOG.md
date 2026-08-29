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
| Primary metric | Not yet implemented |
| Versioned evaluation cases | Not yet implemented |
| Human time | Not measured |
| Runtime per evaluated case | Not measured |
| External API cost | Not measured |

The regression-suite result proves that the existing application behavior passed
its automated tests. It is not an accuracy or safety result.

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

