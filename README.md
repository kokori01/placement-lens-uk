# PlacementLens UK

[![CI](https://github.com/kokori01/placement-lens-uk/actions/workflows/ci.yml/badge.svg)](https://github.com/kokori01/placement-lens-uk/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

PlacementLens UK is an explainable, API-backed career-intelligence platform for UK data roles. It combines public job feeds, a privacy-conscious candidate profile, hybrid ranking, normalized SQL analytics, a FastAPI service and a responsive dashboard.

## What it demonstrates

- **Data engineering:** bounded ingestion from The Muse, Jobicy and selected Greenhouse job boards; provenance, freshness checks and URL deduplication.
- **Data science:** normalized skill extraction, weighted coverage, evidence confidence, title/level fit and TF-IDF text similarity.
- **Analytics:** a normalized SQLite warehouse for jobs, levels, skills, candidates and immutable ranking runs.
- **Software engineering:** test-first provider adapters, dependency-injected network clients, FastAPI endpoints and a production-style dashboard.
- **Responsible data:** no LinkedIn/Indeed scraping, no credentials in source control and clickable canonical links for every live job.

## Verified portfolio evidence

- **39 automated tests** cover ingestion contracts, geographic and temporal filters, ranking, evaluation, normalized storage, analytics, API routes and the repository demo.
- **60-source-record audit:** 44 The Muse, 9 Greenhouse and 7 Jobicy adverts in the bounded 2026-07-23 snapshot.
- **Relational analytics:** normalized jobs, sources, levels, skills, candidates and immutable ranking runs in SQLite.
- **Honest evaluation:** Precision@K, NDCG@K and MRR@K are implemented, but no model-quality claim is made before human relevance labels exist.

## Architecture

```mermaid
flowchart LR
    A[Permitted job APIs] --> B[Provider adapters]
    B --> C[Validation, provenance and deduplication]
    C --> D[Hybrid explainable ranker]
    P[Private candidate profile] --> D
    D --> E[(Normalized SQLite warehouse)]
    E --> F[FastAPI analytics]
    F --> G[Responsive dashboard]
    D --> H[Human relevance labels]
    H --> I[Precision@K, NDCG@K, MRR@K]
```

## Current live snapshot

The bounded 2026-07-23 audit contains 60 unique records:

| Source | Records |
|---|---:|
| The Muse | 44 |
| Jobicy | 7 |
| Greenhouse | 9 |

Live artifacts under `data/raw`, `data/processed` and the private candidate profile under `data/private` are gitignored. See [`docs/SOURCES.md`](docs/SOURCES.md) for official documentation, source decisions, attribution and audit limitations.

### Snapshot insight

The audit is useful as market intelligence, not as a claim that all records are suitable vacancies. It contains 42 senior, 13 mid-level, three unspecified, one internship and one entry-level role. Among the 60 adverts, 49 (81.7%) mention at least one skill in the curated taxonomy; the most frequent are Python (30), SQL (28), AWS (17), GCP (17), Azure (15), data analysis (14), ETL (12) and machine learning (8).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Run tests

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

## Run the fictional end-to-end demo

The demo inputs contain no real candidate or employer data. This path exercises ranking and warehouse construction without API calls.

```bash
mkdir -p output/demo

PYTHONPATH=src .venv/bin/python -m placement_lens.cli rank \
  --candidate examples/candidate.demo.json \
  --jobs examples/jobs.demo.json \
  --output output/demo/ranked.json

PYTHONPATH=src .venv/bin/python -m placement_lens.cli build-db \
  --jobs examples/jobs.demo.json \
  --candidate examples/candidate.demo.json \
  --ranked output/demo/ranked.json \
  --database output/demo/placement_lens.db \
  --model-version hybrid-v1-demo

PYTHONPATH=src .venv/bin/python -m placement_lens.cli serve \
  --database output/demo/placement_lens.db \
  --host 127.0.0.1 \
  --port 8765
```

## Refresh the live pipeline

Use explicit date bounds so a run is reproducible and future source timestamps cannot enter silently.

```bash
PYTHONPATH=src .venv/bin/python -m placement_lens.cli fetch-themuse \
  --pages 5 \
  --published-after 2026-01-01 \
  --output data/processed/themuse_london_data_since_2026.json

PYTHONPATH=src .venv/bin/python -m placement_lens.cli fetch-jobicy \
  --count 50 \
  --tag 'data science' \
  --published-after 2026-01-01 \
  --output data/processed/jobicy_remote_data_since_2026.json

PYTHONPATH=src .venv/bin/python -m placement_lens.cli fetch-greenhouse \
  --updated-after 2026-01-01 \
  --updated-before 2026-07-23 \
  --output data/processed/greenhouse_uk_data_2026-07-23.json

PYTHONPATH=src .venv/bin/python -m placement_lens.cli merge-jobs \
  --input data/processed/themuse_london_data_since_2026.json \
  --input data/processed/jobicy_remote_data_since_2026.json \
  --input data/processed/greenhouse_uk_data_2026-07-23.json \
  --output data/processed/jobs_combined_since_2026.json
```

## Rank against a candidate profile

`examples/candidate.demo.json` is fictional. A real CV-derived profile should remain under `data/private/` and must not contain contact details.

```bash
cp examples/candidate.demo.json data/private/candidate.local.json
# Edit only skills, target levels/title terms and evidence; omit contact details.
```

```bash
PYTHONPATH=src .venv/bin/python -m placement_lens.cli rank \
  --candidate data/private/candidate.local.json \
  --jobs data/processed/jobs_combined_since_2026.json \
  --output data/processed/jobs_combined_ranked.local.json
```

The JSON output exposes overall score, weighted skill coverage, evidence confidence, title fit, level fit, TF-IDF similarity, matched skills and missing skills. It also preserves the source URL and whether the source timestamp means `published` or `updated`.

## Build SQL analytics and run the dashboard

```bash
PYTHONPATH=src .venv/bin/python -m placement_lens.cli build-db \
  --jobs data/processed/jobs_combined_since_2026.json \
  --candidate data/private/candidate.local.json \
  --ranked data/processed/jobs_combined_ranked.local.json \
  --database data/processed/placement_lens.db \
  --model-version hybrid-v1

PYTHONPATH=src .venv/bin/python -m placement_lens.cli serve \
  --database data/processed/placement_lens.db \
  --host 127.0.0.1 \
  --port 8765
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). JSON endpoints are available at `/api/health`, `/api/summary`, `/api/skills`, `/api/gaps` and `/api/jobs`.

## Ranking evaluation

Model-quality metrics are produced only after human review; blank labels are never treated as negatives.

```bash
PYTHONPATH=src .venv/bin/python -m placement_lens.cli create-labels \
  --ranked data/processed/jobs_combined_ranked.local.json \
  --output data/private/relevance_labels.csv \
  --limit 30

# Fill relevance with 0–3, then:
PYTHONPATH=src .venv/bin/python -m placement_lens.cli evaluate \
  --ranked data/processed/jobs_combined_ranked.local.json \
  --labels data/private/relevance_labels.csv \
  --k 10
```

Reported metrics are Precision@K, NDCG@K and MRR@K. Until the CSV is reviewed by a human, the project makes no model-quality claim.

## Limitations

- The active snapshot currently contains only one internship and one entry-level role; most records are useful for market intelligence rather than direct placement applications.
- The Greenhouse registry is intentionally finite and employer-specific, not a full-market crawl.
- An API record may be stale or closed. Verify each opportunity on its canonical source page.
- The next highest-yield UK sources are Adzuna and Reed, both of which require developer credentials.
