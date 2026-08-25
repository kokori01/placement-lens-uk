# PlacementLens UK — Product Brief

## User

An international MSc Data Science student seeking a UK placement in Data Science, Data Analytics or Machine Learning Engineering.

## Problem

Job adverts are fragmented and inconsistent. Candidates struggle to identify which roles fit, which skills recur, and which gaps are worth closing.

## Core promise

Turn permitted UK job-advert data into an explainable priority list and evidence-based learning plan.

## MVP acceptance criteria

- Read candidate and job records from JSON.
- Normalize a curated data-skill taxonomy from free text.
- Score each role using required-skill coverage.
- Return score, matched skills and missing skills.
- Sort roles deterministically.
- Cover core behavior with automated tests.
- Run with Python 3.9+ and no external runtime dependency.

## Later milestones

1. Permitted live API ingestion and PostgreSQL warehouse.
2. SQL/dbt analytics models and market dashboard.
3. TF-IDF baseline versus embedding-based semantic ranker.
4. Offline ranking evaluation with Precision@K, Recall@K and NDCG@K.
5. FastAPI, Docker, CI/CD, deployment and monitoring.

## Responsible-data constraint

Use official open data and licensed APIs. Do not bypass access controls or scrape sources in breach of their terms.
