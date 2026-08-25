"""Human-label evaluation utilities for ranking quality."""

import csv
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List


def _dcg(relevances: Iterable[int]) -> float:
    return sum(
        ((2 ** relevance) - 1) / math.log2(position + 2)
        for position, relevance in enumerate(relevances)
    )


def evaluate_ranking(
    ranked_job_ids: Iterable[str],
    relevance_labels: Dict[str, int],
    *,
    k: int = 10,
) -> Dict[str, Any]:
    """Calculate Precision@K, NDCG@K and MRR@K on human-labeled jobs."""
    if k < 1:
        raise ValueError("k must be at least 1")
    labeled_ranking = [
        job_id for job_id in ranked_job_ids if job_id in relevance_labels
    ]
    selected = labeled_ranking[:k]
    relevances = [relevance_labels[job_id] for job_id in selected]
    evaluated_at_k = len(selected)
    precision = (
        sum(relevance > 0 for relevance in relevances) / evaluated_at_k
        if evaluated_at_k
        else 0.0
    )
    ideal_relevances = sorted(relevance_labels.values(), reverse=True)[:evaluated_at_k]
    ideal_dcg = _dcg(ideal_relevances)
    ndcg = _dcg(relevances) / ideal_dcg if ideal_dcg else 0.0
    reciprocal_rank = 0.0
    for position, relevance in enumerate(relevances, 1):
        if relevance > 0:
            reciprocal_rank = 1 / position
            break
    return {
        "k": k,
        "labeled_jobs": len(relevance_labels),
        "evaluated_at_k": evaluated_at_k,
        "precision_at_k": round(precision, 4),
        "ndcg_at_k": round(ndcg, 4),
        "mrr_at_k": round(reciprocal_rank, 4),
    }


def write_label_template(
    ranked_payload: Dict[str, Any],
    output_path: Path,
    *,
    limit: int = 30,
) -> None:
    """Export ranked jobs for manual 0–3 relevance review."""
    fieldnames = [
        "job_id",
        "title",
        "company",
        "source",
        "source_url",
        "relevance",
        "notes",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for job in ranked_payload.get("ranked_jobs", [])[:limit]:
            writer.writerow(
                {
                    "job_id": job.get("job_id", ""),
                    "title": job.get("title", ""),
                    "company": job.get("company", ""),
                    "source": job.get("source", ""),
                    "source_url": job.get("source_url", ""),
                    "relevance": "",
                    "notes": "",
                }
            )


def load_relevance_labels(path: Path) -> Dict[str, int]:
    """Load reviewed labels, skipping rows that have not been labeled yet."""
    labels: Dict[str, int] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            raw_relevance = (row.get("relevance") or "").strip()
            if not raw_relevance:
                continue
            relevance = int(raw_relevance)
            if relevance not in {0, 1, 2, 3}:
                raise ValueError("Relevance labels must be integers from 0 to 3")
            job_id = (row.get("job_id") or "").strip()
            if not job_id:
                raise ValueError("Every labeled row must have a job_id")
            labels[job_id] = relevance
    return labels
