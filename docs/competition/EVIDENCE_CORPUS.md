# Approved agricultural evidence corpus

Status: Issue #7 corpus v1, curated 2026-08-29.

Plant AI uses a reviewed local evidence collection instead of scraping the web
during a scan. The machine-readable source of truth is
[`Flask/evidence/corpus-v1.json`](../../Flask/evidence/corpus-v1.json).

## Reproducibility contract

- Corpus version: `plant-ai-evidence-2026-08-29-v1`.
- Each retrieved record includes its stable ID, HTTPS source URL, source name,
  retrieval date, geographic scope, corpus version, and corpus SHA-256.
- Summaries and actions are short human-curated paraphrases. Published page text
  is not copied into the repository.
- No network request, crawler, embedding service, or LLM is used during
  retrieval. Exact normalized crop and condition aliases determine a match.
- A scan retrieves at most two records. No match or any retrieval error returns
  no treatment claim and directs the user to local extension or a plant clinic.
- Product names, pesticide rates, and spray schedules are excluded because
  registrations, labels, resistance, crop stage, and local conditions vary.

## Approved v1 sources

| Stable source ID | Crop and condition | Authority | Geographic scope |
| --- | --- | --- | --- |
| `unh-extension-apple-scab` | Apple / apple scab | [University of New Hampshire Extension](https://extension.unh.edu/resource/apple-scab-fact-sheet) | New England; confirm varieties and pesticides locally |
| `umn-extension-corn-common-rust` | Corn / common rust | [University of Minnesota Extension](https://extension.umn.edu/agriculture/crop-production/corn/common-rust-on-corn) | Upper Midwest; disease pressure varies locally |
| `iastate-extension-grape-black-rot` | Grape / black rot | [Iowa State University Extension and Outreach](https://yardandgarden.extension.iastate.edu/encyclopedia/black-rot-grape) | Iowa and similar settings; local timing and registration apply |
| `uc-ipm-potato-early-blight` | Potato / early blight | [UC Statewide IPM Program](https://ipm.ucanr.edu/agriculture/potato/early-blight/) | California production guidance |
| `umn-extension-tomato-potato-late-blight` | Tomato or potato / late blight | [University of Minnesota Extension](https://extension.umn.edu/agriculture/specialty-crops/vegetable-farming/disease-management/late-blight) | Minnesota garden and farm guidance |
| `uc-ipm-bean-anthracnose` | Common bean / anthracnose | [UC Statewide IPM Program](https://ipm.ucanr.edu/agriculture/dry-beans/bean-anthracnose/) | California dry-bean guidance |
| `uc-ipm-bean-rust` | Common bean / bean rust | [UC Statewide IPM Program](https://ipm.ucanr.edu/home-and-landscape/bean-rust/) | California home and landscape guidance |

## Retrieval and presentation

The LangGraph `evidence_retrieval` node runs after the final local or AI-assisted
crop/condition candidate is available. It cannot change that identification.
It returns only exact in-scope evidence, and every management action carries the
record's source ID, name, and URL. Results show the source beside each action and
display a concise evidence card with regional limitations.

Paid scan records preserve the retrieved records and corpus version. Existing
MariaDB/SQLite installations receive two additive nullable columns at startup;
older records remain valid.

## Updating the corpus

Treat a corpus change as a measured application change:

1. verify the source remains authoritative and publicly linkable;
2. write a concise paraphrase and avoid copying substantial source text;
3. record the retrieval date and geographic limitations;
4. assign a new stable source ID for a materially different publication;
5. increment `corpus_version` for any content or scope change;
6. run evidence, workflow, route, persistence, and evaluation tests; and
7. commit the resulting corpus hash and experiment result.

The project does not bypass robots.txt, access controls, or website terms. If a
source cannot be reviewed lawfully and reproducibly, it is not added.
