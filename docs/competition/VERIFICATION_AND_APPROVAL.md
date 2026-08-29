# Verification and human approval

Status: Issue #8 implementation, 2026-08-29.

The workflow is a screening tool, not an autonomous treatment decision-maker.
After evidence retrieval, the `verification` node records a visible human
checkpoint before any treatment decision. The checkpoint is pending by default
and includes machine-readable reasons when the case needs extra scrutiny:

- selected confidence is below the configured local threshold;
- the top two models disagree on crop with a margin below 0.15; or
- no approved crop-and-condition guidance was found.

The checkpoint never silently approves a pesticide, product, rate, or dosage.
The evidence corpus contains cultural next steps and local-confirmation prompts,
not product instructions. A report that cannot be supported receives no
condition-specific treatment advice. A required-tool failure escalates to a
qualified plant-health professional or laboratory.

## State and trace contract

Every completed preliminary report includes:

- `review_checkpoint.approval = pending`;
- `review_checkpoint.status` (`review_required` or `review_recommended`);
- a bounded list of review reasons; and
- a plain-language message to confirm the crop and condition before treatment.

The trace includes a `verification` event with only the number of reasons. It
does not include image bytes, prompts, account data, or private history.
Clarification reports use status `blocked` until the requested context is
provided. Non-plant uploads terminate before verification and classification.

## Threshold rationale and limits

The 0.75 local confidence threshold is an operational guardrail inherited from
the earlier workflow, not a calibrated probability. The 0.15 disagreement
margin is a conservative review signal for materially conflicting model crops.
Neither threshold proves a disease or image quality. Issue #11 will add
representative trajectory artifacts, and future calibration work should measure
these gates against expert-reviewed images.

## Frozen-case check

On the evidence-aware v2 manifest, the verification-enabled agent retained the
5/13 correct-and-safe rate and 4/13 critical-violation cases from the retrieval
stage. Seven plant cases were marked `review_required`, two low-confidence cases
were `blocked` pending context, and two were `review_recommended`; non-plant
rejections terminate before a checkpoint. The machine-readable trace is
[`results/agent-verification-v2.json`](results/agent-verification-v2.json).
