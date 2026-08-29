# Plant AI Field Triage Agent — five-minute demo script

Target duration: 4 minutes 30 seconds. All claims below are backed by committed
artifacts on the `agent` branch; do not present a screening result as a confirmed
diagnosis or treatment authorization.

## 0:00–0:35 — Problem and user

Show the home page and say: “A grower or extension officer often has a leaf
photo but lacks a fast, reviewable first triage. Plant AI screens plant leaves,
compares every registered crop model, requests missing context, and keeps a
human checkpoint before treatment.”

Evidence: [`PROBLEM_AND_METRICS.md`](PROBLEM_AND_METRICS.md),
[`AGENT_ARCHITECTURE.md`](AGENT_ARCHITECTURE.md).

## 0:35–1:25 — Normal plant scan

Upload a clear tomato or bean leaf. Point out the preview, optional crop and
symptom context, and the “scanning every model” message. Submit and show model
votes, the preliminary label, source-backed next steps, the approved evidence
card, and the pending human review checkpoint.

Evidence: [`EVIDENCE_CORPUS.md`](EVIDENCE_CORPUS.md),
[`VERIFICATION_AND_APPROVAL.md`](VERIFICATION_AND_APPROVAL.md).

## 1:25–2:10 — Uncertain and non-plant paths

Upload a blurred leaf or leave symptoms blank. Show that Plant AI asks only for
the missing symptom field, makes no diagnosis, and does not consume the trial
allowance. Upload a car or document and show that the leaf gate rejects it before
any disease model runs.

Evidence: [`trajectories/representative-v1.json`](trajectories/representative-v1.json),
the `clarification_for_missing_symptoms` and `nonplant_rejection` trajectories.

## 2:10–2:55 — Evidence and history

Show a matching cited source beside a management action. Explain that the local
corpus is hashed and region-scoped, unsupported crops receive no treatment
guidance, and premium users see only their own five newest matching history
records. Open a saved record to show model evidence, source provenance, and the
privacy note.

Evidence: [`EVIDENCE_CORPUS.md`](EVIDENCE_CORPUS.md),
[`CONTEXT_AND_MEMORY.md`](CONTEXT_AND_MEMORY.md).

## 2:55–3:40 — Agent design and safety

Show the architecture diagram and one trajectory. Call out the bounded AI retry,
evidence retrieval, verification reasons, safe-failure escalation, and pending
approval state. State clearly: “The system does not choose a pesticide, dosage,
or application schedule.”

Evidence: [`AGENT_ARCHITECTURE.md`](AGENT_ARCHITECTURE.md),
[`TRAJECTORIES.md`](TRAJECTORIES.md).

## 3:40–4:30 — Measured improvement and reproducibility

Show the v2 comparison: correct-and-safe triage moved from 4/13 to 5/13 and
unsupported management violations fell from 6 to 2. Mention that crop/condition
accuracy stayed at 44.4%, so this is an evidence-safety gain, not a vision
accuracy claim. Finish by running `python scripts\smoke_test.py` or showing its
passing output, then point judges to the clean-clone guide.

Evidence: [`EVIDENCE_RETRIEVAL_RESULTS_V2.md`](EVIDENCE_RETRIEVAL_RESULTS_V2.md),
[`REPRODUCIBILITY.md`](REPRODUCIBILITY.md),
[`IMPROVEMENT_CHANGELOG.md`](IMPROVEMENT_CHANGELOG.md).

## Recording checklist

- Use test images or fixture data with redistribution rights documented.
- Do not show `.env`, database credentials, API keys, user emails, or private
  history.
- Keep the video at or below five minutes and use the exact measured numbers.
- Include the branch/commit in the description and link the artifacts above.
