# Competition rubric evidence audit

Audit date: 2026-08-29. Branch: `agent`.

| Rubric area | Evidence in repository | Status |
| --- | --- | --- |
| Problem and user bottleneck | `PROBLEM_AND_METRICS.md`, README | Ready |
| Agent solution and engineering | `AGENT_ARCHITECTURE.md`, LangGraph workflow, five trajectories | Ready |
| Context and memory | `CONTEXT_AND_MEMORY.md`, ownership/retention tests | Ready |
| Evidence and citations | `EVIDENCE_CORPUS.md`, corpus hash, v2 manifest/results | Ready |
| Safety and human control | `VERIFICATION_AND_APPROVAL.md`, rejection/abstention/safe-failure traces | Ready |
| Measured improvement | `BASELINE_RESULTS_V1.md`, `EVIDENCE_RETRIEVAL_RESULTS_V2.md`, changelog | Ready |
| Reproducibility | `REPRODUCIBILITY.md`, lock file, smoke test, evaluation README | Ready |
| Privacy and secret handling | `.gitignore`, `.env.example`, sanitized traces, credential disclosure note | Ready with owner credential-revocation action |
| Five-minute demo | `DEMO_SCRIPT.md` | Recording required |
| Video claims | Must use the exact committed metrics and limitations in the script | Recording required |

## Measured headline

On the same 13 image assets and labels, evidence-aware v2 improved correct-and-
safe triage from 4/13 (30.8%) to 5/13 (38.5%) and reduced unsupported management
violations from 6 to 2. Crop and condition accuracy remained 44.4%. The agent
does not claim definitive diagnosis or autonomous treatment.

## Remaining pre-submission actions

1. Record and review the demo using `DEMO_SCRIPT.md` (less than five minutes).
2. Revoke any credential that appeared in older public history and decide whether
   history rewriting is required before publishing.
3. Run the clean-clone smoke test and link the final video URL in the submission.
