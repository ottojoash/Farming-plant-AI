# Representative agent trajectories

The readable, machine-generated artifact is
[`trajectories/representative-v1.json`](trajectories/representative-v1.json).
It is captured from deterministic fixture tools and linked to the exact source
commit recorded in the artifact. It contains no uploaded image bytes, user
history, credentials, prompts, or hidden chain-of-thought.

## Covered paths

| Trajectory | Path demonstrated |
| --- | --- |
| `local_evidence_success` | Intake → leaf gate → all vision tools → approved evidence → verification → local report |
| `nonplant_rejection` | Intake → leaf gate → rejection before disease models |
| `clarification_for_missing_symptoms` | Low confidence → targeted request for missing symptoms; no diagnosis or allowance use |
| `required_tool_safe_failure` | Vision tool exception → safe escalation with no diagnosis |
| `bounded_ai_retry` | Low confidence with complete context → two-attempt AI retry → evidence → verification → AI report |

Each trace event includes sequence, node, status, sanitized detail, duration,
and attempt where relevant. Outputs include only disposition, labels, review
state, source IDs, requested fields, and errors. Source URLs and full evidence
summaries remain in the versioned corpus and result UI; they are not duplicated
in trajectory output.

## Re-capture

From the repository root, after installing dependencies:

```powershell
python scripts\capture_trajectories.py
```

The script uses fixture image bytes and callbacks, so it does not need datasets,
MariaDB, OpenAI, or Flutterwave credentials. Review the resulting source commit,
trace fields, and secret scan before committing a new artifact version.
