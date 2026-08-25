"""Read-only SQL analytics used by the API and dashboard."""

import sqlite3
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional


def _resolve_run_id(
    connection: sqlite3.Connection,
    run_id: Optional[int],
) -> int:
    if run_id is not None:
        return run_id
    row = connection.execute("SELECT MAX(run_id) FROM ranking_runs").fetchone()
    if not row or row[0] is None:
        raise ValueError("No ranking run is available")
    return int(row[0])


def _round_one(value: Any) -> float:
    return float(Decimal(str(value or 0.0)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def get_summary(
    connection: sqlite3.Connection,
    *,
    run_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Return headline metrics for a ranking run."""
    resolved_run_id = _resolve_run_id(connection, run_id)
    total_jobs = connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    sources = connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    target_level_jobs = connection.execute(
        """
        SELECT COUNT(DISTINCT job_key)
        FROM job_levels
        WHERE level IN ('Internship', 'Entry Level')
        """
    ).fetchone()[0]
    score_row = connection.execute(
        """
        SELECT AVG(overall_score), MAX(overall_score)
        FROM ranking_results
        WHERE run_id = ?
        """,
        (resolved_run_id,),
    ).fetchone()
    latest_publication = connection.execute(
        "SELECT MAX(published_at) FROM jobs"
    ).fetchone()[0]
    return {
        "run_id": resolved_run_id,
        "total_jobs": int(total_jobs),
        "sources": int(sources),
        "target_level_jobs": int(target_level_jobs),
        "average_score": _round_one(score_row[0]),
        "top_score": _round_one(score_row[1]),
        "latest_publication": latest_publication or "",
    }


def get_skill_demand(
    connection: sqlite3.Connection,
    *,
    limit: int = 15,
) -> List[Dict[str, Any]]:
    """Return number of adverts mentioning each normalized skill."""
    rows = connection.execute(
        """
        SELECT s.name, COUNT(*) AS demand
        FROM job_skills js
        JOIN skills s ON s.skill_id = js.skill_id
        GROUP BY s.skill_id, s.name
        ORDER BY demand DESC, s.name ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [{"skill": str(skill), "count": int(count)} for skill, count in rows]


def get_skill_gaps(
    connection: sqlite3.Connection,
    *,
    run_id: Optional[int] = None,
    limit: int = 15,
) -> List[Dict[str, Any]]:
    """Return skills marked missing in one explainable ranking run."""
    resolved_run_id = _resolve_run_id(connection, run_id)
    rows = connection.execute(
        """
        SELECT s.name, COUNT(*) AS gap_count
        FROM ranking_result_skills rrs
        JOIN skills s ON s.skill_id = rrs.skill_id
        WHERE rrs.run_id = ? AND rrs.status = 'missing'
        GROUP BY s.skill_id, s.name
        ORDER BY gap_count DESC, s.name ASC
        LIMIT ?
        """,
        (resolved_run_id, limit),
    ).fetchall()
    return [{"skill": str(skill), "count": int(count)} for skill, count in rows]


def _split_group(value: Optional[str]) -> List[str]:
    return value.split("|") if value else []


def get_ranked_jobs(
    connection: sqlite3.Connection,
    *,
    run_id: Optional[int] = None,
    source: str = "",
    level: str = "",
    limit: int = 25,
) -> List[Dict[str, Any]]:
    """Return ranked jobs with optional source and level filters."""
    resolved_run_id = _resolve_run_id(connection, run_id)
    rows = connection.execute(
        """
        SELECT
            rr.rank_position,
            j.job_key,
            j.title,
            j.company,
            j.location,
            src.name,
            j.source_url,
            j.published_at,
            j.timestamp_kind,
            rr.overall_score,
            rr.skill_coverage,
            rr.skill_confidence,
            rr.skill_score,
            rr.title_score,
            rr.text_score,
            rr.level_score,
            (
                SELECT GROUP_CONCAT(jl.level, '|')
                FROM job_levels jl
                WHERE jl.job_key = j.job_key
            ) AS levels,
            (
                SELECT GROUP_CONCAT(s.name, '|')
                FROM ranking_result_skills rrs
                JOIN skills s ON s.skill_id = rrs.skill_id
                WHERE rrs.run_id = rr.run_id
                  AND rrs.job_key = rr.job_key
                  AND rrs.status = 'matched'
            ) AS matched_skills,
            (
                SELECT GROUP_CONCAT(s.name, '|')
                FROM ranking_result_skills rrs
                JOIN skills s ON s.skill_id = rrs.skill_id
                WHERE rrs.run_id = rr.run_id
                  AND rrs.job_key = rr.job_key
                  AND rrs.status = 'missing'
            ) AS missing_skills
        FROM ranking_results rr
        JOIN jobs j ON j.job_key = rr.job_key
        JOIN sources src ON src.source_id = j.source_id
        WHERE rr.run_id = ?
          AND (? = '' OR src.name = ?)
          AND (
              ? = '' OR EXISTS (
                  SELECT 1 FROM job_levels filter_level
                  WHERE filter_level.job_key = j.job_key
                    AND filter_level.level = ?
              )
          )
        ORDER BY rr.rank_position
        LIMIT ?
        """,
        (
            resolved_run_id,
            source,
            source,
            level,
            level,
            max(1, min(limit, 200)),
        ),
    ).fetchall()
    return [
        {
            "rank": int(row[0]),
            "job_id": str(row[1]),
            "title": str(row[2]),
            "company": str(row[3]),
            "location": str(row[4]),
            "source": str(row[5]),
            "source_url": str(row[6]),
            "published_at": str(row[7]),
            "timestamp_kind": str(row[8]),
            "score": float(row[9]),
            "skill_coverage": float(row[10]),
            "skill_confidence": float(row[11]),
            "skill_score": float(row[12]),
            "title_score": float(row[13]),
            "text_score": float(row[14]),
            "level_score": float(row[15]),
            "levels": _split_group(row[16]),
            "matched_skills": _split_group(row[17]),
            "missing_skills": _split_group(row[18]),
        }
        for row in rows
    ]
