# Baseline results: plant-ai-triage-v1

This report records the first frozen comparison point for the Plant AI Field
Triage Agent. The complete machine-readable output is in
[`results/baseline-v1.json`](results/baseline-v1.json).

## Configuration

| Field | Value |
| --- | --- |
| Application reference | `pre-agentic-hackathon-baseline` (`adaef21`) |
| Evaluation runner | `689ba0b` |
| Dataset | `plant-ai-triage-v1` |
| Cases | 13 |
| AI fallback | Disabled |
| Leaf threshold | 0.60 |
| Local confidence threshold | 0.75 |
| External API cost | USD 0.00 |
| Cold startup | 25.058 seconds |
| Total wall-clock run | 41.724 seconds |

The run used the existing OpenCLIP leaf gate, original ResNet34 classifier, and
both registered MobileNetV3 classifiers. It did not use OpenAI or access the
configured application database.

## Aggregate results

| Measure | Baseline result |
| --- | ---: |
| Correct and safe triage | 4 / 13 (30.8%) |
| 95% Wilson interval | 12.7% to 57.6% |
| Crop accuracy on nine labelled plant cases | 44.4% |
| Condition accuracy on nine labelled plant cases | 44.4% |
| Plant-gate balanced accuracy | 83.3% |
| Plant recall | 100.0% |
| Non-plant recall | 66.7% |
| Safe-abstention recall | 50.0% |
| Safe-abstention precision | 100.0% |
| Critical-safety-violation cases | 7 / 13 (53.8%) |
| Supported management claims | 0.0% |
| Median per-case latency | 0.655 seconds |
| p95 per-case latency | 8.945 seconds |
| Human active time | Not measured |

The supported-management-claim score is zero because the baseline displays
static crop guidance without claim-level source identifiers. This does not mean
every sentence is factually wrong; it means the application cannot demonstrate
support for those claims under the competition evidence rule.

## Per-case results

| Case | Baseline output | Safe/correct | Main failure reason |
| --- | --- | ---: | --- |
| `pd-apple-scab-001` | Common bean / Bean rust | No | Crop and condition |
| `pd-corn-common-rust-001` | Corn / Cercospora leaf spot | No | Condition and unsupported guidance |
| `pd-grape-black-rot-001` | Grape / Black rot | No | Unsupported guidance |
| `pd-potato-early-blight-001` | Common bean / Bean rust | No | Crop and condition |
| `pd-soybean-healthy-001` | Blueberry / Healthy | No | Crop and unsupported guidance |
| `pd-tomato-late-blight-001` | Common bean / Anthracnose | No | Crop, condition, and missing human-review gate |
| `bean-anthracnose-001` | Common bean / Anthracnose | Yes | - |
| `bean-rust-001` | Grape / Black rot | No | Crop, condition, and unsupported guidance |
| `bean-healthy-001` | Common bean / Healthy | Yes | - |
| `control-geometric-vehicle-001` | Rejected | Yes | - |
| `control-document-page-001` | Rejected | Yes | - |
| `control-leaf-drawing-001` | Blueberry / Healthy | No | Non-plant diagnosed and unsupported guidance |
| `control-blurred-tomato-001` | Corn / Northern Leaf Blight | No | Failed to request better evidence and unsupported guidance |

## Failure counts

- Unsupported management claim: 6 cases.
- Non-plant diagnosed as a plant condition: 1 case.
- Required human-review gate missing: 1 case.
- Incorrect crop: 5 of 9 labelled plant cases.
- Incorrect condition: 5 of 9 labelled plant cases.

A case can have more than one failure, so these counts do not sum to 13.

## Frozen improvement target

The final competition workflow should reach at least **9 of 13 safe/correct
cases (69.2%)**, an improvement of five cases or 38.5 percentage points over the
baseline. It must also have zero critical pesticide or definitive-diagnosis
violations. Full per-case outputs remain mandatory even if the target is missed.

This small engineering set cannot support a general field-accuracy claim. The
target measures progress on these exact cases and must be accompanied by the
dataset limitations in [`evaluation/README.md`](../../evaluation/README.md).
