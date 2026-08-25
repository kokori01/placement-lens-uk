# Job-data sources and provenance

This document records source selection, usage constraints and the bounded live audit performed on 2026-07-23. Live snapshots are local, gitignored artifacts; test fixtures are fictional or reduced records.

## Active sources

| Source | Official documentation | Authentication | Segment | Stored source time |
|---|---|---:|---|---|
| The Muse | [Public Jobs API v2](https://www.themuse.com/developers/api/v2) and [terms](https://www.themuse.com/developers/api/v2/terms) | None | Exact `London, United Kingdom` + `Data and Analytics` records | Publication time (`timestamp_kind=published`) |
| Jobicy | [Jobs API/RSS documentation](https://jobicy.com/jobs-rss-feed) | None | Remote data roles explicitly open to UK/Europe/EMEA/Anywhere | Publication time (`timestamp_kind=published`) |
| Greenhouse | [Job Board API](https://developers.greenhouse.io/job-board.html) | None for public board GETs | UK data/ML titles from a bounded employer registry | Board update time (`timestamp_kind=updated`) |

Every normalized record retains:

- source and provider record ID;
- canonical/clickable source URL;
- company, title and description;
- location and normalized level;
- source timestamp and its semantic kind.

Jobicy explicitly asks users of its content to provide a clickable source link. PlacementLens preserves the source URL through ingestion, ranking, SQL storage and dashboard display for every provider.

## Greenhouse registry

The active registry is deliberately finite rather than an unbounded crawl:

- Monzo
- Wayve
- Anthropic
- PhysicsX
- Grafana Labs
- Stripe
- GoCardless

Only titles matching the data/analytics/ML role contract and explicit UK locations are accepted. The live command also requires an explicit lower and upper update-date bound. This protects the dataset from source timestamps that are unexpectedly in the future.

## Live audit: 2026-07-23

After freshness, geography and role validation:

| Source | Accepted records |
|---|---:|
| The Muse | 44 |
| Jobicy | 7 |
| Greenhouse | 9 |
| **Combined** | **60** |

Combined quality checks:

- 60 unique source URLs;
- 0 duplicate source URLs;
- 0 missing source URLs;
- 51 publication timestamps and 9 update timestamps;
- 0 Greenhouse timestamps after the explicit `2026-07-23` cutoff;
- 81.7% of descriptions contain at least one skill recognized by the current taxonomy.

The snapshot contains only two target-level records (one internship and one entry-level role). The other records remain useful for market-demand and skill-gap analysis, but they must not be represented as placement opportunities.

## Researched but not active

| Source | Probe result | Decision |
|---|---|---|
| Arbeitnow | Five pages returned 650 records. Nine records passed strict UK data-role title filtering, but all nine `created_at` values resolved to 2026-08-24 or 2026-08-25—after the verified system date. | Rejected from the active snapshot because temporal integrity failed. Re-evaluate later. |
| Remotive | `search=data` returned 18 jobs; only two target-title records had eligible Europe/worldwide geography, and both were senior. | Not integrated because incremental UK placement yield was negligible. |
| Lever Postings API | A bounded employer-slug probe produced only one relevant UK result in the tested set. | Not integrated because yield was lower than Greenhouse. |
| Adzuna | UK-focused search API with useful salary/location fields; official developer registration provides an API key. | Strong next source once credentials are supplied through environment variables. |
| Reed | UK-focused search API requiring developer credentials. | Strong next source once credentials are available. |

Official research links:

- [Arbeitnow Job Board API](https://www.arbeitnow.com/api/job-board-api)
- [Remotive public API](https://remotive.com/api/remote-jobs)
- [Lever Postings API](https://github.com/lever/postings-api)
- [Adzuna developer portal](https://developer.adzuna.com/)
- [Reed developer portal](https://www.reed.co.uk/developers)

## Interpretation limits

An API response proves that the provider returned a record at fetch time. It does not guarantee that the vacancy remains open, that the candidate is eligible, or that the role is suitable. Ranking scores are prioritization signals—not interview probabilities. Always verify status and requirements on the canonical source page before applying.
