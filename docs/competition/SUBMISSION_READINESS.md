# Frontier Engineering Challenge 2026 — submission readiness

Checked against the live HackerEarth challenge page on 2026-08-29:
<https://www.hackerearth.com/community/challenges/hackathon/micro1-frontier-engineering-challenge-2026/>

## Challenge gates

| Requirement | Evidence on `agent` | Status |
|---|---|---|
| Individual entry | The repository is prepared for one owner; the challenge allows team size 1. | Ready |
| Agentic solution | LangGraph workflow: intake → leaf gate → model ensemble → evidence retrieval → verification → final response. | Ready |
| Baseline and meaningful advanced solution | Frozen pre-agentic baseline and the evidence-aware, verification-enabled agent are both documented and evaluated on versioned cases. | Ready |
| Complete code and improvement changelog | Repository source plus [`IMPROVEMENT_CHANGELOG.md`](IMPROVEMENT_CHANGELOG.md). | Ready |
| Clean-environment reproduction | [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md), Python 3.11 lock snapshot, smoke test, and offline evaluation commands. | Ready |
| Solution video (maximum 5 minutes) | [`plant-ai-demo.mp4`](plant-ai-demo.mp4) is a 2:25 narrated demo. | Needs external hosting URL |
| Representative agent trajectories | Sanitized success, rejection, clarification, retry, safe-failure, evidence, and verification trajectories in [`TRAJECTORIES.md`](TRAJECTORIES.md). | Ready |
| Human control for consequential actions | The verification checkpoint requires approval before treatment guidance; non-plant and uncertain cases terminate or escalate safely. | Ready |
| Reproducible evidence for claims | Versioned manifests, raw JSON results, source IDs, and rubric audit are committed. | Ready |
| Credentials and private data excluded | No active credentials are required by the evaluation. Revoke any historical key that was previously exposed before making the repository public. | Owner action |

## What remains before clicking Submit

1. Upload `plant-ai-demo.mp4` to a permitted public host (for example YouTube or Vimeo) and paste the resulting URL into HackerEarth. A local file path cannot satisfy a hosted-video field.
2. If the form asks for a live demo URL, deploy the application to a public service or mark the demo unavailable. The current project is reproducible locally but is not deployed by this repository.
3. Register as one individual, confirm eligibility, and submit the `agent` branch/repository URL. Only the latest complete submission is evaluated.
4. Revoke and rotate any credential that appeared in old commits or screenshots, then verify the final public repository contains no secrets.

## Assessment

The implementation is technically ready for the challenge's engineering gates. Submission is not yet complete because HackerEarth requires an externally hosted video URL (and may request a public demo URL), and the final click must be performed from the participant's authenticated HackerEarth account. No HackerEarth submission connector or account authorization is available in this workspace, so those external steps cannot be completed automatically.

