"""Command-line interface for the first PlacementLens UK vertical MVP."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable, List, Optional, TextIO

import uvicorn

from placement_lens.api import create_app
from placement_lens.evaluation import (
    evaluate_ranking,
    load_relevance_labels,
    write_label_template,
)
from placement_lens.matching import (
    CandidateProfile,
    JobPosting,
    extract_skills,
    rank_jobs,
)
from placement_lens.sources.greenhouse import fetch_greenhouse_jobs
from placement_lens.sources.jobicy import fetch_jobicy_jobs
from placement_lens.sources.themuse import fetch_jobs as fetch_themuse_jobs
from placement_lens.storage import (
    initialize_database,
    load_candidate,
    load_jobs,
    load_ranking_run,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="placement-lens")
    subparsers = parser.add_subparsers(dest="command", required=True)
    rank_parser = subparsers.add_parser("rank", help="rank job adverts for a candidate")
    rank_parser.add_argument("--candidate", required=True, type=Path)
    rank_parser.add_argument("--jobs", required=True, type=Path)
    rank_parser.add_argument("--output", type=Path)
    rank_parser.add_argument("--level", dest="levels", action="append")

    fetch_parser = subparsers.add_parser(
        "fetch-themuse", help="fetch normalized London jobs from The Muse"
    )
    fetch_parser.add_argument("--output", required=True, type=Path)
    fetch_parser.add_argument("--pages", type=int, default=3)
    fetch_parser.add_argument("--location", default="London, United Kingdom")
    fetch_parser.add_argument("--category", default="Data and Analytics")
    fetch_parser.add_argument("--published-after")

    jobicy_parser = subparsers.add_parser(
        "fetch-jobicy", help="fetch eligible remote data jobs from Jobicy"
    )
    jobicy_parser.add_argument("--output", required=True, type=Path)
    jobicy_parser.add_argument("--count", type=int, default=50)
    jobicy_parser.add_argument("--tag", default="data science")
    jobicy_parser.add_argument("--published-after")

    greenhouse_parser = subparsers.add_parser(
        "fetch-greenhouse", help="fetch bounded UK data jobs from selected public boards"
    )
    greenhouse_parser.add_argument("--output", required=True, type=Path)
    greenhouse_parser.add_argument("--updated-after")
    greenhouse_parser.add_argument("--updated-before")

    merge_parser = subparsers.add_parser(
        "merge-jobs", help="merge normalized job files and remove duplicate URLs"
    )
    merge_parser.add_argument("--input", dest="inputs", action="append", required=True, type=Path)
    merge_parser.add_argument("--output", required=True, type=Path)

    database_parser = subparsers.add_parser(
        "build-db", help="load normalized jobs and rankings into SQLite"
    )
    database_parser.add_argument("--jobs", required=True, type=Path)
    database_parser.add_argument("--candidate", required=True, type=Path)
    database_parser.add_argument("--ranked", required=True, type=Path)
    database_parser.add_argument("--database", required=True, type=Path)
    database_parser.add_argument("--model-version", default="hybrid-v1")

    serve_parser = subparsers.add_parser("serve", help="serve the API and dashboard")
    serve_parser.add_argument("--database", required=True, type=Path)
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", default=8000, type=int)

    labels_parser = subparsers.add_parser(
        "create-labels", help="export ranked jobs for manual relevance review"
    )
    labels_parser.add_argument("--ranked", required=True, type=Path)
    labels_parser.add_argument("--output", required=True, type=Path)
    labels_parser.add_argument("--limit", default=30, type=int)

    evaluate_parser = subparsers.add_parser(
        "evaluate", help="evaluate a ranking against reviewed relevance labels"
    )
    evaluate_parser.add_argument("--ranked", required=True, type=Path)
    evaluate_parser.add_argument("--labels", required=True, type=Path)
    evaluate_parser.add_argument("--k", default=10, type=int)
    return parser


def _job_to_record(job: JobPosting) -> dict:
    return {
        "id": job.job_id,
        "title": job.title,
        "company": job.company,
        "description": job.description,
        "location": job.location,
        "levels": list(job.levels),
        "source": job.source,
        "source_url": job.source_url,
        "published_at": job.published_at,
        "timestamp_kind": job.timestamp_kind,
    }


def _write_records(records: List[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main(
    argv: Optional[List[str]] = None,
    *,
    stdout: TextIO = sys.stdout,
    themuse_fetcher: Callable[..., List[JobPosting]] = fetch_themuse_jobs,
    jobicy_fetcher: Callable[..., List[JobPosting]] = fetch_jobicy_jobs,
    greenhouse_fetcher: Callable[..., List[JobPosting]] = fetch_greenhouse_jobs,
    server_runner: Callable[..., Any] = uvicorn.run,
) -> int:
    """Run the PlacementLens command-line interface."""
    args = _build_parser().parse_args(argv)

    if args.command in {"fetch-themuse", "fetch-jobicy", "fetch-greenhouse"}:
        if args.command == "fetch-themuse":
            jobs = themuse_fetcher(
                location=args.location,
                category=args.category,
                pages=args.pages,
                published_after=args.published_after,
            )
            source_name = "The Muse"
        elif args.command == "fetch-jobicy":
            jobs = jobicy_fetcher(
                count=args.count,
                tag=args.tag,
                published_after=args.published_after,
            )
            source_name = "Jobicy"
        else:
            jobs = greenhouse_fetcher(
                updated_after=args.updated_after,
                updated_before=args.updated_before,
            )
            source_name = "Greenhouse"
        records = [_job_to_record(job) for job in jobs]
        _write_records(records, args.output)
        json.dump(
            {"source": source_name, "records": len(records), "output": str(args.output)},
            stdout,
            indent=2,
        )
        stdout.write("\n")
        return 0

    if args.command == "merge-jobs":
        records = []
        seen = set()
        for input_path in args.inputs:
            for record in json.loads(input_path.read_text(encoding="utf-8")):
                deduplication_key = record.get("source_url") or (
                    f"{record.get('source', '')}:{record.get('id', '')}"
                )
                if deduplication_key in seen:
                    continue
                seen.add(deduplication_key)
                records.append(record)
        _write_records(records, args.output)
        json.dump(
            {"records": len(records), "output": str(args.output)},
            stdout,
            indent=2,
        )
        stdout.write("\n")
        return 0

    if args.command == "build-db":
        jobs_data = json.loads(args.jobs.read_text(encoding="utf-8"))
        candidate_data = json.loads(args.candidate.read_text(encoding="utf-8"))
        ranked_payload = json.loads(args.ranked.read_text(encoding="utf-8"))
        args.database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(args.database) as connection:
            initialize_database(connection)
            load_jobs(connection, jobs_data)
            load_candidate(connection, candidate_data)
            run_id = load_ranking_run(
                connection,
                candidate_id=candidate_data["candidate_id"],
                payload=ranked_payload,
                model_version=args.model_version,
            )
        json.dump(
            {
                "database": str(args.database),
                "jobs": len(jobs_data),
                "run_id": run_id,
                "model_version": args.model_version,
            },
            stdout,
            indent=2,
        )
        stdout.write("\n")
        return 0

    if args.command == "serve":
        server_runner(
            create_app(args.database),
            host=args.host,
            port=args.port,
        )
        return 0

    if args.command == "create-labels":
        ranked_payload = json.loads(args.ranked.read_text(encoding="utf-8"))
        write_label_template(ranked_payload, args.output, limit=args.limit)
        json.dump(
            {"records": min(args.limit, len(ranked_payload.get("ranked_jobs", []))),
             "output": str(args.output)},
            stdout,
            indent=2,
        )
        stdout.write("\n")
        return 0

    if args.command == "evaluate":
        ranked_payload = json.loads(args.ranked.read_text(encoding="utf-8"))
        ranked_job_ids = [
            item["job_id"] for item in ranked_payload.get("ranked_jobs", [])
        ]
        metrics = evaluate_ranking(
            ranked_job_ids,
            load_relevance_labels(args.labels),
            k=args.k,
        )
        json.dump(metrics, stdout, indent=2)
        stdout.write("\n")
        return 0

    candidate_data = json.loads(args.candidate.read_text(encoding="utf-8"))
    jobs_data = json.loads(args.jobs.read_text(encoding="utf-8"))
    if args.levels:
        allowed_levels = set(args.levels)
        jobs_data = [
            item
            for item in jobs_data
            if allowed_levels.intersection(item.get("levels", []))
        ]

    candidate_skills = extract_skills(" ; ".join(candidate_data["skills"]))
    candidate = CandidateProfile(
        skills=frozenset(candidate_skills),
        target_levels=frozenset(candidate_data.get("target_levels", [])),
        preferred_title_terms=tuple(candidate_data.get("preferred_title_terms", [])),
        profile_text=candidate_data.get("profile_text", ""),
    )
    jobs = [
        JobPosting(
            job_id=item["id"],
            title=item["title"],
            company=item["company"],
            description=item["description"],
            location=item.get("location", ""),
            levels=tuple(item.get("levels", [])),
            source=item.get("source", ""),
            source_url=item.get("source_url", ""),
            published_at=item.get("published_at", ""),
            timestamp_kind=item.get("timestamp_kind", "published"),
        )
        for item in jobs_data
    ]

    ranked_jobs = rank_jobs(candidate, jobs)
    payload = {
        "candidate_skills": sorted(candidate.skills),
        "ranked_jobs": [
            {
                "job_id": item.job.job_id,
                "title": item.job.title,
                "company": item.job.company,
                "location": item.job.location,
                "levels": list(item.job.levels),
                "source": item.job.source,
                "source_url": item.job.source_url,
                "published_at": item.job.published_at,
                "timestamp_kind": item.job.timestamp_kind,
                "score": item.match.score,
                "skill_coverage": item.match.skill_coverage,
                "skill_confidence": item.match.skill_confidence,
                "skill_score": item.match.skill_score,
                "title_score": item.match.title_score,
                "text_score": item.match.text_score,
                "level_score": item.match.level_score,
                "matched_skills": list(item.match.matched_skills),
                "missing_skills": list(item.match.missing_skills),
            }
            for item in ranked_jobs
        ],
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        json.dump(
            {"records": len(ranked_jobs), "output": str(args.output)},
            stdout,
            indent=2,
        )
    else:
        json.dump(payload, stdout, indent=2)
    stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
