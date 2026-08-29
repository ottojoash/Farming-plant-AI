# Context and plant-history memory

Status: Issue #6 implementation, 2026-08-29.

Plant AI now combines a photo with optional field context and, for paid users,
a small set of relevant records from their own scan history. The feature is
designed to improve triage continuity without turning private account data into
an unbounded prompt or trace.

## Intake contract

The scan form accepts five optional, length-bounded fields:

| Field | Maximum length | Persisted with the scan |
| --- | ---: | --- |
| Reported crop | 120 characters | Crop may already be part of the diagnosis record; the intake value itself is not stored. |
| Location | 120 characters | No |
| Visible symptoms | 500 characters | No |
| Symptom duration | 80 characters | No |
| Recent treatment | 300 characters | No |

These values are run-scoped. Raw image bytes, free-text context, model prompts,
and history contents are excluded from agent traces and evaluation artifacts.
The intake trace records only the number of supplied fields and retrieved
records.

When all local model candidates are below the configured confidence threshold,
the workflow pauses rather than presenting a weak diagnosis. It asks only for
the missing critical fields: reported crop and visible symptoms. A paused scan
does not consume an anonymous or free-account allowance.

## Memory policy

Plant-history memory is derived from the existing `ScanRecord` table and does
not introduce a second store:

- only authenticated monthly or yearly accounts can retrieve memory;
- every query is scoped to the current user's account ID;
- records must match the user-reported crop case-insensitively;
- at most the five newest matching records enter workflow state; and
- anonymous and free accounts receive no history, even if a record exists.

The agent uses relevant history only to qualify its output. For example, a
matching previous crop and condition produces a recurrence note and a stronger
recommendation to seek local confirmation. History never overrides the current
image models or creates a disease prediction by itself.

Deleting an account removes its scan records through the existing database
relationship. Images are not retained in scan history; records contain only
diagnostic metadata. This stage does not persist location, symptoms, duration,
or treatment history.

## Known limitations

- Exact crop matching depends on the user naming the crop consistently.
- The frozen evaluation cases contain no account history, so memory behavior is
  verified by workflow and authenticated-route tests rather than the v1
  benchmark.
- Context must currently be entered again if the workflow requests another
  image; preserving a draft would require an explicit short-lived retention
  policy.
