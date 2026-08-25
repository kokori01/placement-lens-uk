"""Normalized SQLite analytics layer for jobs, skills and ranking runs."""

import sqlite3
from typing import Any, Dict, Iterable, List, Tuple

from placement_lens.matching import extract_skills


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    source_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS jobs (
    job_key TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    description TEXT NOT NULL,
    location TEXT NOT NULL,
    source_id INTEGER NOT NULL REFERENCES sources(source_id),
    source_url TEXT NOT NULL UNIQUE,
    published_at TEXT NOT NULL,
    timestamp_kind TEXT NOT NULL DEFAULT 'published'
);

CREATE TABLE IF NOT EXISTS job_levels (
    job_key TEXT NOT NULL REFERENCES jobs(job_key) ON DELETE CASCADE,
    level TEXT NOT NULL,
    PRIMARY KEY (job_key, level)
);

CREATE TABLE IF NOT EXISTS skills (
    skill_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS job_skills (
    job_key TEXT NOT NULL REFERENCES jobs(job_key) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skills(skill_id),
    PRIMARY KEY (job_key, skill_id)
);

CREATE TABLE IF NOT EXISTS candidates (
    candidate_id TEXT PRIMARY KEY,
    target_location TEXT NOT NULL,
    profile_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_skills (
    candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skills(skill_id),
    evidence TEXT NOT NULL,
    PRIMARY KEY (candidate_id, skill_id)
);

CREATE TABLE IF NOT EXISTS ranking_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
    model_version TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ranking_results (
    run_id INTEGER NOT NULL REFERENCES ranking_runs(run_id) ON DELETE CASCADE,
    job_key TEXT NOT NULL REFERENCES jobs(job_key),
    rank_position INTEGER NOT NULL,
    overall_score REAL NOT NULL,
    skill_coverage REAL NOT NULL,
    skill_confidence REAL NOT NULL,
    skill_score REAL NOT NULL,
    title_score REAL NOT NULL,
    text_score REAL NOT NULL,
    level_score REAL NOT NULL,
    PRIMARY KEY (run_id, job_key),
    UNIQUE (run_id, rank_position)
);

CREATE TABLE IF NOT EXISTS ranking_result_skills (
    run_id INTEGER NOT NULL,
    job_key TEXT NOT NULL,
    skill_id INTEGER NOT NULL REFERENCES skills(skill_id),
    status TEXT NOT NULL CHECK (status IN ('matched', 'missing')),
    PRIMARY KEY (run_id, job_key, skill_id),
    FOREIGN KEY (run_id, job_key)
        REFERENCES ranking_results(run_id, job_key) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_jobs_published_at ON jobs(published_at);
CREATE INDEX IF NOT EXISTS idx_jobs_source_id ON jobs(source_id);
CREATE INDEX IF NOT EXISTS idx_job_skills_skill_id ON job_skills(skill_id);
CREATE INDEX IF NOT EXISTS idx_ranking_results_score
    ON ranking_results(run_id, overall_score DESC);
"""


def initialize_database(connection: sqlite3.Connection) -> None:
    """Create all analytics tables and indexes."""
    connection.executescript(SCHEMA)
    job_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
    }
    if "timestamp_kind" not in job_columns:
        connection.execute(
            "ALTER TABLE jobs ADD COLUMN timestamp_kind TEXT NOT NULL DEFAULT 'published'"
        )


def _skill_id(connection: sqlite3.Connection, skill: str) -> int:
    connection.execute(
        "INSERT OR IGNORE INTO skills(name) VALUES (?)",
        (skill,),
    )
    row = connection.execute(
        "SELECT skill_id FROM skills WHERE name = ?",
        (skill,),
    ).fetchone()
    return int(row[0])


def load_jobs(
    connection: sqlite3.Connection,
    records: Iterable[Dict[str, Any]],
) -> None:
    """Upsert normalized jobs and rebuild their level/skill bridges."""
    with connection:
        for record in records:
            source_name = record.get("source", "Unknown")
            connection.execute(
                "INSERT OR IGNORE INTO sources(name) VALUES (?)",
                (source_name,),
            )
            source_id = connection.execute(
                "SELECT source_id FROM sources WHERE name = ?",
                (source_name,),
            ).fetchone()[0]
            job_key = str(record["id"])
            connection.execute(
                """
                INSERT INTO jobs(
                    job_key, title, company, description, location,
                    source_id, source_url, published_at, timestamp_kind
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_key) DO UPDATE SET
                    title = excluded.title,
                    company = excluded.company,
                    description = excluded.description,
                    location = excluded.location,
                    source_id = excluded.source_id,
                    source_url = excluded.source_url,
                    published_at = excluded.published_at,
                    timestamp_kind = excluded.timestamp_kind
                """,
                (
                    job_key,
                    record.get("title", ""),
                    record.get("company", ""),
                    record.get("description", ""),
                    record.get("location", ""),
                    source_id,
                    record.get("source_url", ""),
                    record.get("published_at", ""),
                    record.get("timestamp_kind", "published"),
                ),
            )
            connection.execute("DELETE FROM job_levels WHERE job_key = ?", (job_key,))
            connection.execute("DELETE FROM job_skills WHERE job_key = ?", (job_key,))
            connection.executemany(
                "INSERT INTO job_levels(job_key, level) VALUES (?, ?)",
                [(job_key, level) for level in record.get("levels", [])],
            )
            for skill in sorted(extract_skills(record.get("description", ""))):
                connection.execute(
                    "INSERT INTO job_skills(job_key, skill_id) VALUES (?, ?)",
                    (job_key, _skill_id(connection, skill)),
                )


def load_candidate(
    connection: sqlite3.Connection,
    candidate: Dict[str, Any],
) -> None:
    """Upsert a privacy-conscious candidate profile and its evidenced skills."""
    candidate_id = candidate["candidate_id"]
    evidence = {
        name.casefold(): value
        for name, value in candidate.get("skill_evidence", {}).items()
    }
    normalized_skills = extract_skills(" ; ".join(candidate.get("skills", [])))
    with connection:
        connection.execute(
            """
            INSERT INTO candidates(candidate_id, target_location, profile_text)
            VALUES (?, ?, ?)
            ON CONFLICT(candidate_id) DO UPDATE SET
                target_location = excluded.target_location,
                profile_text = excluded.profile_text
            """,
            (
                candidate_id,
                candidate.get("target_location", ""),
                candidate.get("profile_text", ""),
            ),
        )
        connection.execute(
            "DELETE FROM candidate_skills WHERE candidate_id = ?",
            (candidate_id,),
        )
        for skill in sorted(normalized_skills):
            connection.execute(
                """
                INSERT INTO candidate_skills(candidate_id, skill_id, evidence)
                VALUES (?, ?, ?)
                """,
                (candidate_id, _skill_id(connection, skill), evidence.get(skill, "")),
            )


def load_ranking_run(
    connection: sqlite3.Connection,
    *,
    candidate_id: str,
    payload: Dict[str, Any],
    model_version: str,
) -> int:
    """Store an immutable ranking run and all explainability components."""
    with connection:
        cursor = connection.execute(
            "INSERT INTO ranking_runs(candidate_id, model_version) VALUES (?, ?)",
            (candidate_id, model_version),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("Ranking run ID was not generated")
        run_id = int(cursor.lastrowid)
        for rank_position, result in enumerate(payload.get("ranked_jobs", []), 1):
            job_key = str(result["job_id"])
            connection.execute(
                """
                INSERT INTO ranking_results(
                    run_id, job_key, rank_position, overall_score,
                    skill_coverage, skill_confidence, skill_score,
                    title_score, text_score, level_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    job_key,
                    rank_position,
                    result.get("score", 0.0),
                    result.get("skill_coverage", 0.0),
                    result.get("skill_confidence", 0.0),
                    result.get("skill_score", 0.0),
                    result.get("title_score", 0.0),
                    result.get("text_score", 0.0),
                    result.get("level_score", 0.0),
                ),
            )
            for status, key in (
                ("matched", "matched_skills"),
                ("missing", "missing_skills"),
            ):
                for skill in result.get(key, []):
                    connection.execute(
                        """
                        INSERT INTO ranking_result_skills(
                            run_id, job_key, skill_id, status
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (run_id, job_key, _skill_id(connection, skill), status),
                    )
    return run_id


def top_demanded_skills(
    connection: sqlite3.Connection,
    *,
    limit: int = 10,
) -> List[Tuple[str, int]]:
    """Return skill document frequency using a normalized SQL join."""
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
    return [(str(name), int(demand)) for name, demand in rows]
